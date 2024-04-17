# This script finds all PDF files, counts the number of pages in each, and summarizes the distribution of page counts.

# Ensure PDFtk is in your system's PATH or specify its path directly
$pdftkPath = "pdftk"

# Get all PDF files in the current directory and its subdirectories
$pdfFiles = Get-ChildItem -Recurse -Filter *.pdf

# Initialize a hashtable to keep track of page count distribution
$pageCountDistribution = @{}

# Loop through each PDF file
foreach ($pdf in $pdfFiles) {
    # Use PDFtk to dump PDF metadata
    $pdfInfo = & $pdftkPath $pdf.FullName dump_data 2>&1
    
    # Check for password protection error
    if ($pdfInfo -like "*OWNER PASSWORD REQUIRED*") {
        Write-Output "Skipping password protected file: $($pdf.FullName)"
        continue
    }
    
    # Extract the number of pages from the metadata
    $pages = ($pdfInfo | Where-Object { $_ -match "NumberOfPages" }) -replace "NumberOfPages: ", ""
    
    # Increment the count for the page number in the distribution hashtable
    if ($pageCountDistribution.ContainsKey($pages)) {
        $pageCountDistribution[$pages]++
    } else {
        $pageCountDistribution[$pages] = 1
    }
}

# Display the distribution of page counts
$pageCountDistribution.Keys | Sort-Object { [int]$_ } | ForEach-Object {
    Write-Output "$_ Page: $($pageCountDistribution[$_]) PDFs"
}
