#requires -Version 5.1
# VPS Control Center RC14 internal module. Dot-sourced by VPS-Control-v7.ps1.

function New-FlatButton([string]$Text, [int]$Width = 150, [int]$Height = 34) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $Text
    $b.Size = New-Object System.Drawing.Size($Width, $Height)
    $b.FlatStyle = 'Flat'
    $b.FlatAppearance.BorderColor = [System.Drawing.Color]::LightGray
    $b.BackColor = [System.Drawing.Color]::White
    $b.UseVisualStyleBackColor = $false
    $b.Cursor = [System.Windows.Forms.Cursors]::Hand
    return $b
}

function New-StatusCard([string]$Title) {
    $panel = New-Object System.Windows.Forms.Panel
    $panel.Width = 216
    $panel.Height = 86
    $panel.Margin = New-Object System.Windows.Forms.Padding(0, 0, 12, 0)
    $panel.BackColor = [System.Drawing.Color]::White
    $panel.BorderStyle = 'FixedSingle'

    $t = New-Object System.Windows.Forms.Label
    $t.Text = $Title
    $t.Location = New-Object System.Drawing.Point(12, 9)
    $t.Size = New-Object System.Drawing.Size(190, 18)
    $t.ForeColor = [System.Drawing.Color]::DimGray
    $panel.Controls.Add($t)

    $v = New-Object System.Windows.Forms.Label
    $v.Text = '—'
    $v.Location = New-Object System.Drawing.Point(12, 31)
    $v.Size = New-Object System.Drawing.Size(190, 24)
    $v.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 11)
    $panel.Controls.Add($v)

    $d = New-Object System.Windows.Forms.Label
    $d.Text = ''
    $d.Location = New-Object System.Drawing.Point(12, 59)
    $d.Size = New-Object System.Drawing.Size(190, 18)
    $d.ForeColor = [System.Drawing.Color]::Gray
    $panel.Controls.Add($d)

    return [pscustomobject]@{ Panel=$panel; Title=$t; Value=$v; Detail=$d }
}
