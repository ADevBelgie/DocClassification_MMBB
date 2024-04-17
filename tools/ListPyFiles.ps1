# Navigate to the src directory relative to the current script location
$srcDirectory = Join-Path -Path $PSScriptRoot -ChildPath "../src"

# Change to the src directory
Set-Location -Path $srcDirectory

# Find all .py files in the src directory
$pyFiles = Get-ChildItem -Filter *.py -Recurse

# Initialize a variable to hold all file contents
$allContent = ""

# Loop through each file, collecting its contents
foreach ($file in $pyFiles) {
    # Add the file name and a divider for clarity to the allContent variable
    $allContent += $file.Name + "`r`n------------------`r`n"
    
    # Add the content of the file
    $content = Get-Content -Path $file.FullName -Raw
    $allContent += $content + "`r`n`r`n"  # Add two new lines for spacing between files
}

# Copy all the content to the clipboard
Set-Clipboard -Value $allContent

# Optionally, you can also output that the content has been copied to the clipboard
Write-Output "All file contents have been copied to the clipboard."
