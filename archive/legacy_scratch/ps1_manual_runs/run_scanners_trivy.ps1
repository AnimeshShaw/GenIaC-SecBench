$AllCompletedModels = @("gpt-4o", "gpt-5", "llama3", "mistral", "phi3", "gemini-2.5-pro", "gemini-3.7-flash")

Write-Host "--- Starting TRIVY Loop ---"
foreach ($model in $AllCompletedModels) {
    Write-Host "Running Trivy on model: $model"
    python src/phase3_scanning/run_scanners.py --scanner trivy --model $model
}
Write-Host "Sequential scanning complete for Trivy."
