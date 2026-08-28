$CompletedModels = @("gpt-5", "llama3", "mistral", "phi3", "gemini-2.5-pro", "gemini-3.7-flash")
$AllCompletedModels = @("gpt-4o", "gpt-5", "llama3", "mistral", "phi3", "gemini-2.5-pro", "gemini-3.7-flash")

# Checkov loop (skip gpt-4o since it's already running/done via task-1026)
Write-Host "--- Starting CHECKOV Loop ---"
foreach ($model in $CompletedModels) {
    Write-Host "Running Checkov on model: $model"
    python src/phase3_scanning/run_scanners.py --scanner checkov --model $model
}

# Trivy loop
Write-Host "--- Starting TRIVY Loop ---"
foreach ($model in $AllCompletedModels) {
    Write-Host "Running Trivy on model: $model"
    python src/phase3_scanning/run_scanners.py --scanner trivy --model $model
}

# KICS loop
Write-Host "--- Starting KICS Loop ---"
foreach ($model in $AllCompletedModels) {
    Write-Host "Running KICS on model: $model"
    python src/phase3_scanning/run_scanners.py --scanner kics --model $model
}

Write-Host "Sequential scanning complete for all finished models."
