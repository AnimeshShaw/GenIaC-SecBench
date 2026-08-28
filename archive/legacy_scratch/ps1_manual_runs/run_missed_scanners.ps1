$AllCompletedModels = @("gpt-4o", "gpt-5", "llama3", "mistral", "phi3", "gemini-3.1-pro", "gemini-3.7-flash")

# Trivy loop for all
Write-Host "--- Starting TRIVY Loop ---"
foreach ($model in $AllCompletedModels) {
    Write-Host "Running Trivy on model: $model"
    python src/phase3_scanning/run_scanners.py --scanner trivy --model $model
}

# Checkov & KICS for gemini-3.1-pro only (since it was skipped earlier due to the typo)
Write-Host "--- Starting Missed Checkov/KICS for gemini-3.1-pro ---"
python src/phase3_scanning/run_scanners.py --scanner checkov --model gemini-3.1-pro
python src/phase3_scanning/run_scanners.py --scanner kics --model gemini-3.1-pro

Write-Host "Sequential scanning complete for all missed items."
