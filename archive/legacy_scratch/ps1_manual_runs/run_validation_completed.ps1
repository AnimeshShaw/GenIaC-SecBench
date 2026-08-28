$CompletedModels = @("gpt-4o", "gpt-5", "llama3", "mistral", "phi3", "gemini-3.1-pro", "gemini-3.7-flash")

foreach ($model in $CompletedModels) {
    Write-Host "Starting validation for model: $model (simple)"
    python src/phase2_validation/validate_iac.py --model $model --dataset simple

    Write-Host "Starting validation for model: $model (complex)"
    python src/phase2_validation/validate_iac.py --model $model --dataset complex
}

Write-Host "Validation complete for all finished models. Claude models are skipped until they finish generation."
