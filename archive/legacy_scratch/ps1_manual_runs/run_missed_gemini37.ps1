Write-Host "Running Phase 2 Validation for gemini-3.7-flash..."
python src/phase2_validation/validate_iac.py --model gemini-3.7-flash

Write-Host "Running Phase 3 Scanners for gemini-3.7-flash..."
python src/phase3_scanning/run_scanners.py --scanner checkov --model gemini-3.7-flash
python src/phase3_scanning/run_scanners.py --scanner trivy --model gemini-3.7-flash
python src/phase3_scanning/run_scanners.py --scanner kics --model gemini-3.7-flash

Write-Host "Parsing results..."
python src/phase3_scanning/parse_results.py

Write-Host "Done!"
