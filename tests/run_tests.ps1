# PowerShell script to run all tests
Set-Location "C:\Users\konfu\Desktop\sigmatradebot"

Write-Host "=" -NoNewline
Write-Host ("=" * 79)
Write-Host "RUNNING ALL UNIT TESTS"
Write-Host "=" -NoNewline
Write-Host ("=" * 79)
Write-Host ""

$testFiles = @(
    "tests/unit/test_settings.py",
    "tests/unit/test_main_menu_keyboard.py",
    "tests/unit/test_deposit_validation_service.py",
    "tests/unit/test_withdrawal_service.py",
    "tests/unit/test_referral_service.py",
    "tests/unit/models/test_user.py",
    "tests/unit/models/test_deposit.py",
    "tests/unit/models/test_transaction.py",
    "tests/unit/models/test_referral.py",
    "tests/unit/models/test_referral_earning.py",
    "tests/unit/repositories/test_user_repository.py",
    "tests/unit/repositories/test_deposit_repository.py",
    "tests/unit/repositories/test_transaction_repository.py",
    "tests/unit/services/test_user_service.py",
    "tests/unit/services/test_transaction_service.py",
    "tests/unit/services/test_reward_service.py",
    "tests/unit/services/test_deposit_service.py"
)

$resultsFile = "test_results_powershell.txt"
$passed = 0
$failed = 0

"TEST EXECUTION RESULTS" | Out-File -FilePath $resultsFile -Encoding utf8
("=" * 80) | Out-File -FilePath $resultsFile -Append -Encoding utf8
"" | Out-File -FilePath $resultsFile -Append -Encoding utf8

for ($i = 0; $i -lt $testFiles.Count; $i++) {
    $testFile = $testFiles[$i]
    $num = $i + 1
    
    Write-Host "[$num/$($testFiles.Count)] Running: $testFile"
    
    ("`n" + ("=" * 80)) | Out-File -FilePath $resultsFile -Append -Encoding utf8
    ("[$num/$($testFiles.Count)] $testFile") | Out-File -FilePath $resultsFile -Append -Encoding utf8
    ("=" * 80) | Out-File -FilePath $resultsFile -Append -Encoding utf8
    
    $result = python -m pytest $testFile -v --tb=short 2>&1
    
    $result | Out-File -FilePath $resultsFile -Append -Encoding utf8
    
    if ($LASTEXITCODE -eq 0) {
        $passed++
        Write-Host "  ✅ PASSED" -ForegroundColor Green
        "`n✅ PASSED" | Out-File -FilePath $resultsFile -Append -Encoding utf8
    } else {
        $failed++
        Write-Host "  ❌ FAILED (exit code: $LASTEXITCODE)" -ForegroundColor Red
        "`n❌ FAILED (exit code: $LASTEXITCODE)" | Out-File -FilePath $resultsFile -Append -Encoding utf8
    }
}

Write-Host ""
Write-Host "=" -NoNewline
Write-Host ("=" * 79)
Write-Host "SUMMARY: $passed passed, $failed failed out of $($testFiles.Count)"
Write-Host "=" -NoNewline
Write-Host ("=" * 79)
Write-Host "Results saved to: $resultsFile"

("`n" + ("=" * 80)) | Out-File -FilePath $resultsFile -Append -Encoding utf8
("SUMMARY: $passed passed, $failed failed out of $($testFiles.Count)") | Out-File -FilePath $resultsFile -Append -Encoding utf8
("=" * 80) | Out-File -FilePath $resultsFile -Append -Encoding utf8

