$CompletedModels = @("gpt-4o", "gpt-5", "llama3", "mistral", "phi3", "gemini-2.5-pro", "gemini-3.7-flash")

foreach ($model in $CompletedModels) {
    Write-Host "Starting scanning for model: $model"
    python src/phase3_scanning/run_scanners.py --model $model
}

Write-Host "Scanning complete for all finished models."
