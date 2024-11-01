param(
    [string]$FileName,
    [string]$FolderName,
    [string]$DealsPath = "Z:\Zoho CRM\Deals",
    [string]$AccountsPath = "Z:\Zoho CRM\Accounts"
)

function Get-FlexibleFileName {
    param([string]$FileName)
    # Replace colons with single character wildcard, but keep the rest specific
    return $FileName -replace ':', '?'
}

function Search-Folder {
    param([string]$FileName, [string]$FolderPath)
    $flexibleFileName = Get-FlexibleFileName $FileName
    
    if (Test-Path $FolderPath) {
        # Use -Filter for faster searching, no -Recurse
        return Get-ChildItem -Path $FolderPath -Filter $flexibleFileName -File | 
               Select-Object -First 1 -ExpandProperty FullName
    }
    return $null
}

function Search-DealsFolder {
    param([string]$FileName, [string]$FolderName, [string]$DealsPath)
    $fullPath = Join-Path -Path $DealsPath -ChildPath $FolderName
    return Search-Folder -FileName $FileName -FolderPath $fullPath
}

function Search-AccountsFolder {
    param([string]$FileName, [string]$FolderName, [string]$AccountsPath)
    foreach ($company in Get-ChildItem -Path $AccountsPath -Directory) {
        $companyPath = Join-Path -Path $company.FullName -ChildPath "Associated Deals"
        $fullPath = Join-Path -Path $companyPath -ChildPath $FolderName
        $result = Search-Folder -FileName $FileName -FolderPath $fullPath
        if ($result) { return $result }
    }
    return $null
}

Write-Host "Searching for file: $FileName"
Write-Host "In folder: $FolderName"
Write-Host "Locations to search: $DealsPath, $AccountsPath"

$sw = [System.Diagnostics.Stopwatch]::StartNew()

$result = Search-DealsFolder -FileName $FileName -FolderName $FolderName -DealsPath $DealsPath
if (-not $result) {
    $result = Search-AccountsFolder -FileName $FileName -FolderName $FolderName -AccountsPath $AccountsPath
}

$sw.Stop()

if ($result) {
    Write-Host "File found: $result"
    Write-Host "RESULT:$result"
} else {
    Write-Host "File not found in any of the specified locations."
    Write-Host "RESULT:NOT_FOUND"
}

Write-Host "Search completed in $($sw.Elapsed.TotalSeconds) seconds."