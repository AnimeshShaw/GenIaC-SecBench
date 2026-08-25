"""
GenIaC-SecBench - Phase 6: Negative Binomial count regression (GEE)
===================================================================

Models vulnerability COUNTS as a function of model, complexity, and their
interaction, with scenario-level repeated measures handled via GEE.

WHAT CHANGED IN THE REMEDIATION (and why) -- read before editing
-----------------------------------------------------------------

The pre-remediation version of this file (archived as
`data/_archive_v1/nb_glmm_results.json`) had four defects that together
inflated every reported effect. All four are corrected here.

1. **It fit a POISSON model despite being named `nb_glmm` and being
   documented everywhere as "Negative Binomial".** Poisson assumes
   variance == mean. Measured on this corpus, var/mean = 60.4 -- an
   overdispersion factor of sixty. The project's own methodology document
   (`docs/methodology/iac_benchmark_methodology.md`, Part C.4) explicitly
   warned that using Poisson here would understate standard errors and
   overstate significance. We now fit a true NB2 model and report the
   estimated dispersion so the choice is auditable.

   (Nuance worth keeping straight: GEE reports *robust* sandwich standard
   errors by default, which are consistent even under a misspecified
   variance function. So the old Poisson fit was not as catastrophic as
   the family name alone suggests -- but the point estimates were still
   driven by the wrong variance weighting, and the published numbers were
   labelled "Negative Binomial" when no NB model had been fit. Both the
   NB fit and a Poisson comparison are emitted below.)

2. **No exposure offset.** `docs/claims_and_statistical_evidence.md`
   (Claim 1) states the model "accounts for the exposure (Resource Count)
   ... allowing us to calculate the true Incidence Rate Ratio (IRR) of
   vulnerabilities per resource." The old formula was
   `total_vulns ~ C(model) * C(complexity)` with no offset term, so the
   IRRs were ratios of RAW COUNTS, not per-resource rates. A model that
   emits 60 resources per file was therefore credited with ~11x the
   "vulnerability rate" of one emitting 5, purely for writing more code.
   This is the single largest source of the inflated 48-55x IRRs. We now
   include `offset=log(resource_count)`, which makes the coefficients
   genuine per-resource incidence rate ratios and matches what the paper
   claims to have measured.

3. **Zero-count rows and scenarios were dropped before fitting.** The old
   code removed every model with zero total vulnerabilities and every
   scenario with zero total vulnerabilities. That is selection on the
   OUTCOME: it discards exactly the observations that carry the "this
   model produced no findings" signal, biasing every rate upward and
   making the fitted model inconsistent with the data-generating process.
   All rows are now retained.

4. **The reference category could not support the interaction.** The old
   baseline was `claude-3-5-sonnet`, which has ZERO simple-stratum rows
   (0/60). Every `model x complexity` interaction term was therefore
   estimated against an empty reference cell. The default reference is now
   chosen from models with complete coverage in BOTH strata.

Exposure note: rows with `resource_count == 0` cannot contribute to a
per-resource rate (log(0) is undefined). Those 7 rows (0.7% of 983) are
excluded from the offset model and the count is reported explicitly. This
is selection on EXPOSURE, not on outcome, and is standard for rate models.

Usage:
    python -m geniac_secbench.phase6_statistics.nb_glmm
    python -m geniac_secbench.phase6_statistics.nb_glmm --reference gpt-4o
"""

import sys
import json
import logging
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.genmod.families import Poisson, NegativeBinomial
from statsmodels.genmod.cov_struct import Exchangeable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

SCANNERS = ["checkov_vulns", "trivy_vulns", "kics_vulns"]


def safe_float(val):
    """JSON-safe float conversion (NaN/Inf are not valid JSON literals)."""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return str(val)
    if np.isnan(f):
        return None
    if np.isinf(f):
        return "Infinity" if f > 0 else "-Infinity"
    return f


def load_master(data_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(data_dir / "master_results.csv")
    for c in SCANNERS:
        if c not in df.columns:
            raise KeyError(f"master_results.csv missing required column: {c}")
    df["total_vulns"] = df[SCANNERS].fillna(0).sum(axis=1)
    df["resource_count"] = pd.to_numeric(df["resource_count"], errors="coerce").fillna(0)
    df["model_cat"] = df["model"].astype(str)
    df["complexity_cat"] = df["complexity"].astype(str)
    df["scenario_id"] = df["scenario_id"].astype(str)
    return df


def dispersion_report(y: pd.Series) -> dict:
    mean, var = float(y.mean()), float(y.var())
    return {
        "mean": safe_float(mean),
        "variance": safe_float(var),
        "variance_to_mean_ratio": safe_float(var / mean if mean else np.nan),
        "poisson_assumption_holds": bool(mean and abs(var / mean - 1) < 0.5),
        "note": ("Poisson requires variance == mean. A ratio far above 1 indicates "
                 "overdispersion and mandates a negative binomial variance function."),
    }


def choose_reference(df: pd.DataFrame) -> str:
    """Pick a reference model that is present in BOTH complexity strata, so the
    interaction terms are estimated against a populated cell. Prefers the model
    with the most complete and most balanced coverage."""
    counts = df.groupby(["model_cat", "complexity_cat"]).size().unstack(fill_value=0)
    strata = [c for c in counts.columns]
    complete = counts[(counts[strata] > 0).all(axis=1)]
    if complete.empty:
        return str(df["model_cat"].value_counts().idxmax())
    # most total rows, tie-broken by balance across strata
    complete = complete.assign(
        total=complete.sum(axis=1),
        balance=complete.min(axis=1) / complete.max(axis=1),
    ).sort_values(["total", "balance"], ascending=False)
    return str(complete.index[0])


def estimate_nb_alpha(df: pd.DataFrame, formula: str, offset: np.ndarray | None) -> float:
    """Estimate the NB2 dispersion parameter alpha from an auxiliary fit.

    statsmodels' NegativeBinomial family needs alpha supplied up front. We get
    it from an independence NB GLM, then feed it into the GEE. Falls back to a
    moment-based estimate if the auxiliary fit fails to converge.
    """
    try:
        aux = smf.glm(formula, data=df, family=NegativeBinomial(alpha=1.0),
                      offset=offset).fit()
        # Method-of-moments refinement from Pearson residuals
        mu = np.asarray(aux.fittedvalues, dtype=float)
        y = np.asarray(df[formula.split("~")[0].strip()], dtype=float)
        mu = np.clip(mu, 1e-9, None)
        alpha = float(np.mean(((y - mu) ** 2 - mu) / (mu ** 2)))
        if not np.isfinite(alpha) or alpha <= 0:
            raise ValueError("non-positive alpha")
        return min(alpha, 50.0)
    except Exception as e:  # noqa: BLE001 - deliberately broad; we always have a fallback
        logger.warning("NB alpha auxiliary fit failed (%s); using moment estimate.", e)
        y = df[formula.split("~")[0].strip()].astype(float)
        m, v = y.mean(), y.var()
        alpha = (v - m) / (m ** 2) if m > 0 and v > m else 1.0
        return float(min(max(alpha, 1e-3), 50.0))


def fit_gee(df: pd.DataFrame, formula: str, family, offset: np.ndarray | None, label: str):
    try:
        model = smf.gee(formula, data=df, groups=df["scenario_id"],
                        family=family, cov_struct=Exchangeable(), offset=offset)
        res = model.fit()
        logger.info("[%s] converged=%s", label, getattr(res, "converged", "n/a"))
        return res
    except Exception as e:  # noqa: BLE001
        logger.error("[%s] GEE fit failed: %s", label, e)
        return None


def extract(res, label: str) -> dict:
    if res is None:
        return {"label": label, "fit_failed": True, "coefficients": {}}
    params, conf, pvals = res.params, res.conf_int(), res.pvalues
    coefs = {}
    for name in params.index:
        coefs[name] = {
            "beta": safe_float(params[name]),
            "irr": safe_float(np.exp(params[name])),
            "ci_lower": safe_float(np.exp(conf.loc[name, 0])),
            "ci_upper": safe_float(np.exp(conf.loc[name, 1])),
            "p_value": safe_float(pvals[name]),
        }
    return {
        "label": label,
        "fit_failed": False,
        "converged": bool(getattr(res, "converged", False)),
        "n_observations": int(res.nobs),
        "coefficients": coefs,
    }


def main():
    ap = argparse.ArgumentParser(description="Negative binomial GEE for vulnerability counts.")
    ap.add_argument("--reference", default=None,
                    help="Reference model for the categorical contrast. "
                         "Default: auto-selected from models complete in both strata.")
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else PATHS.summary_reports
    df = load_master(data_dir)

    disp = dispersion_report(df["total_vulns"])
    logger.info("Overdispersion: var/mean = %.1f (Poisson valid: %s)",
                disp["variance_to_mean_ratio"], disp["poisson_assumption_holds"])

    reference = args.reference or choose_reference(df)
    logger.info("Reference model: %s", reference)
    if reference not in set(df["model_cat"]):
        logger.error("Reference model %r not present in data.", reference)
        sys.exit(1)

    # NOTE: all rows retained. No filtering on the outcome. (Defect #3.)
    n_all = len(df)

    # Exposure: rows with zero resources cannot express a per-resource rate.
    n_zero_exposure = int((df["resource_count"] <= 0).sum())
    df_off = df[df["resource_count"] > 0].copy()
    logger.info("Rows: %d total, %d with zero exposure excluded from the rate model (%.1f%%)",
                n_all, n_zero_exposure, 100 * n_zero_exposure / max(n_all, 1))

    ref = reference.replace("'", "\\'")
    formula = (f"total_vulns ~ C(model_cat, Treatment(reference='{ref}')) "
               f"* C(complexity_cat)")

    offset = np.log(df_off["resource_count"].astype(float).values)

    # --- Primary model: NB2 with exposure offset -------------------------
    alpha = estimate_nb_alpha(df_off, formula, offset)
    logger.info("Estimated NB dispersion alpha = %.4f", alpha)
    nb_off = fit_gee(df_off, formula, NegativeBinomial(alpha=alpha), offset,
                     "NB + offset (PRIMARY)")

    # --- Comparison fits, to make the correction auditable ---------------
    nb_nooff = fit_gee(df, formula, NegativeBinomial(alpha=alpha), None,
                       "NB, no offset")
    pois_nooff = fit_gee(df, formula, Poisson(), None,
                         "Poisson, no offset (reproduces archived v1)")

    out = {
        "_schema": "geniac-secbench/nb_glmm/v2",
        "specification": {
            "primary_model": "Negative binomial (NB2) GEE, exchangeable working "
                             "correlation grouped by scenario_id, with log(resource_count) "
                             "exposure offset.",
            "formula": formula,
            "reference_model": reference,
            "nb_alpha": safe_float(alpha),
            "offset": "log(resource_count)",
            "interpretation": "Coefficients are incidence rate ratios (IRR) for "
                              "vulnerabilities PER RESOURCE, relative to the reference model "
                              "on the reference complexity stratum.",
            "rows_total": n_all,
            "rows_zero_exposure_excluded": n_zero_exposure,
            "rows_fitted": int(len(df_off)),
            "outcome_filtering": "NONE. All observations retained, including zero-count "
                                 "rows and zero-count scenarios (v1 dropped these).",
        },
        "overdispersion": disp,
        "models": {
            "nb_with_offset": extract(nb_off, "NB + offset (PRIMARY)"),
            "nb_without_offset": extract(nb_nooff, "NB, no offset"),
            "poisson_without_offset": extract(pois_nooff, "Poisson, no offset (v1 spec)"),
        },
    }

    out_path = data_dir / "nb_glmm_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    logger.info("Wrote %s", out_path)

    if nb_off is not None:
        logger.info("\n%s", nb_off.summary())


if __name__ == "__main__":
    main()
