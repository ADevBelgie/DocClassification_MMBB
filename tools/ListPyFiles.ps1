# Function to get file contents from a directory
function Get-DirectoryContent($directory, $prefix, $recursive) {
    if ($recursive) {
        $files = Get-ChildItem -Path $directory -Include *.py, *.json, *.md, *.ps1, *.bat -Recurse -File
    } else {
        # For root directory, we'll manually specify the file types
        $files = Get-ChildItem -Path $directory -File | Where-Object { 
            $_.Extension -in @('.py', '.json', '.md', '.ps1', '.bat') -or 
            $_.Name -eq 'README.md'
        }
    }
    $totalFiles = $files.Count
    $processedFiles = 0
    $content = ""

    foreach ($file in $files) {
        $processedFiles++
        $percentComplete = [math]::Round(($processedFiles / $totalFiles) * 100, 2)
        Write-Progress -Activity "Processing $prefix" -Status "$percentComplete% Complete" -PercentComplete $percentComplete

        $relativePath = $file.FullName.Replace($directory, "").TrimStart("\")
        $displayPath = "$prefix/" + $relativePath.Replace("\", "/")
        $content += "$displayPath`r`n------------------`r`n"
        $fileContent = Get-Content -Path $file.FullName -Raw
        $content += "$fileContent`r`n`r`n"
    }
    Write-Progress -Activity "Processing $prefix" -Completed
    return $content
}

# Get the current directory
$currentDirectory = (Get-Location).Path

# Get root directory content (non-recursive)
Write-Host "Processing root directory..."
$rootContent = Get-DirectoryContent $currentDirectory "root" $false

# Get src directory content (recursive)
$srcDirectory = Join-Path -Path $currentDirectory -ChildPath "src"
if (Test-Path $srcDirectory) {
    Write-Host "Processing src directory..."
    $srcContent = Get-DirectoryContent $srcDirectory "src" $true
} else {
    Write-Host "src directory not found. Skipping..."
    $srcContent = ""
}

# Get tests directory content (recursive)
$testsDirectory = Join-Path -Path $currentDirectory -ChildPath "tests"
if (Test-Path $testsDirectory) {
    Write-Host "Processing tests directory..."
    $testsContent = Get-DirectoryContent $testsDirectory "tests" $true
} else {
    Write-Host "tests directory not found. Skipping..."
    $testsContent = ""
}

# Get tools directory content (recursive)
$toolsDirectory = Join-Path -Path $currentDirectory -ChildPath "tools"
if (Test-Path $testsDirectory) {
    Write-Host "Processing tests directory..."
    $toolsContent = Get-DirectoryContent $toolsDirectory "tests" $true
} else {
    Write-Host "tests directory not found. Skipping..."
    $toolsContent = ""
}

# Combine all content
$allContent = $rootContent + $srcContent + $testsContent + $toolsContent

# Copy all the content to the clipboard
Set-Clipboard -Value $allContent

# Output that the content has been copied to the clipboard
Write-Host "All file contents have been copied to the clipboard."