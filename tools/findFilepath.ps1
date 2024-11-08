param(
    [string]$FileName,
    [string]$FolderName,
    [string]$DealsPath = "Z:\Zoho CRM\Deals",
    [string]$AccountsPath = "Z:\Zoho CRM\Accounts"
)

# Ensure consistent encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Get-FlexibleFileName {
    param([string]$FileName)
    # Handle common special characters while keeping pattern specific
    return $FileName -replace ':', '?' `
                    -replace '\[', '`[' `
                    -replace '\]', '`]'
}

function Search-Folder {
    param([string]$FileName, [string]$FolderPath)
    if (-not (Test-Path -LiteralPath $FolderPath)) {
        return $null
    }
    
    # Try exact match first
    $exactPath = Join-Path -Path $FolderPath -ChildPath $FileName
    if (Test-Path -LiteralPath $exactPath) {
        return $exactPath
    }
    
    # Try flexible match
    $flexibleFileName = Get-FlexibleFileName $FileName
    try {
        return Get-ChildItem -Path $FolderPath -Filter $flexibleFileName -File |
               Sort-Object LastWriteTime -Descending |
               Select-Object -First 1 -ExpandProperty FullName
    }
    catch {
        return $null
    }
}

function Search-DealsFolder {
    param([string]$FileName, [string]$FolderName, [string]$DealsPath)
    $fullPath = Join-Path -Path $DealsPath -ChildPath $FolderName
    return Search-Folder -FileName $FileName -FolderPath $fullPath
}

function Search-AccountsFolder {
    param([string]$FileName, [string]$FolderName, [string]$AccountsPath)
    if (-not (Test-Path -LiteralPath $AccountsPath)) {
        return $null
    }
    
    try {
        foreach ($company in Get-ChildItem -Path $AccountsPath -Directory -ErrorAction Stop) {
            $fullPath = Join-Path -Path (Join-Path -Path $company.FullName -ChildPath "Associated Deals") -ChildPath $FolderName
            $result = Search-Folder -FileName $FileName -FolderPath $fullPath
            if ($result) { return $result }
        }
    }
    catch {
        return $null
    }
    return $null
}

# Main execution
$result = Search-DealsFolder -FileName $FileName -FolderName $FolderName -DealsPath $DealsPath
if (-not $result) {
    $result = Search-AccountsFolder -FileName $FileName -FolderName $FolderName -AccountsPath $AccountsPath
}

if ($result) {
    Write-Host "RESULT:$result"
} else {
    Write-Host "RESULT:NOT_FOUND"
}