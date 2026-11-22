param([string]$TextFile, [string]$OutFile, [string]$Title = "library-api", [int]$Width = 1200, [int]$Height = 0, [single]$FontSize = 15)
Add-Type -AssemblyName System.Drawing
$lines = @(Get-Content -LiteralPath $TextFile)
$font = New-Object System.Drawing.Font('Consolas', $FontSize, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$lineHeight = [int][math]::Ceiling($FontSize * 1.42)
$padX = 44; $barH = 44; $padTop = $barH + 22
if ($Height -eq 0) { $Height = $padTop + $lines.Count * $lineHeight + 26 }
$bmp = New-Object System.Drawing.Bitmap($Width, $Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = 'AntiAlias'
$g.TextRenderingHint = 'ClearTypeGridFit'
$g.Clear([System.Drawing.Color]::FromArgb(22, 27, 34))
$bar = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(33, 40, 50))
$g.FillRectangle($bar, 0, 0, $Width, $barH)
$dots = @(@(255,95,86), @(255,189,46), @(39,201,63))
for ($i = 0; $i -lt 3; $i++) {
  $b = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($dots[$i][0], $dots[$i][1], $dots[$i][2]))
  $g.FillEllipse($b, 22 + $i * 24, 15, 14, 14)
}
$titleFont = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$grey = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(139, 148, 158))
$g.DrawString($Title, $titleFont, $grey, 110, 13)
$text = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(230, 237, 243))
$cmd = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(126, 231, 135))
$y = $padTop
foreach ($line in $lines) {
  $brush = $text
  if ($line.StartsWith('$ ')) { $brush = $cmd }
  $g.DrawString($line, $font, $brush, $padX, $y)
  $y += $lineHeight
}
$g.Dispose()
$bmp.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
"wrote $OutFile ${Width}x$Height"
