$ErrorActionPreference = "Stop"

Write-Host "🚀 Turning Buddy - Vercel Deployment Script" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Gray

# Check git status
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "✨ No changes to deploy." -ForegroundColor Green
    exit
}

Write-Host "📝 Files to deploy:" -ForegroundColor Yellow
git status --short

# Get commit message
$commitMsg = Read-Host -Prompt "Enter deployment message (e.g. 'Fix styling')"
if ([string]::IsNullOrWhiteSpace($commitMsg)) {
    $commitMsg = "Update deployment"
}

Write-Host "`n📦 Packaging and Pushing..." -ForegroundColor Cyan

try {
    git add .
    git commit -m "$commitMsg"
    git push origin main
    
    Write-Host "`n✅ Successfully pushed to GitHub!" -ForegroundColor Green
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host "⏳ Vercel is now building your app (wait ~2-3 mins)"
    Write-Host "👉 Check status: https://vercel.com/dashboard"
    Write-Host "💡 REMINDER: Ensure these Environment Variables are set in Vercel:" -ForegroundColor Yellow
    Write-Host "   - DATABASE_URL (Required for Postgres)"
    Write-Host "   - SECRET_KEY (Required)"
    Write-Host "   - GROQ_API_KEY (Required for AI)"
}
catch {
    Write-Host "`n❌ Error during deployment:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Pause
