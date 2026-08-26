Set-StrictMode -Version 3.0

BeforeAll {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $modulePath = Join-Path $repoRoot '.pncc-dev\quality\PNCC.PowerShellCollections.psm1'
    Import-Module -Name $modulePath -Force -ErrorAction Stop
}

Describe 'PNCC PS5.1 stable collection view' {
    It 'normalizes null to an empty Object array' {
        $view = ConvertTo-PnccCollectionView -InputObject $null
        $view.Count | Should -Be 0
        $view.IsEmpty | Should -BeTrue
        $view.Items.GetType().FullName | Should -Be 'System.Object[]'
    }

    It 'normalizes an explicit empty array to zero items' {
        $view = ConvertTo-PnccCollectionView -InputObject @()
        $view.Count | Should -Be 0
        $view.Items.Count | Should -Be 0
    }

    It 'normalizes a scalar value to exactly one item' {
        $view = ConvertTo-PnccCollectionView -InputObject 42
        $view.Count | Should -Be 1
        $view.Items[0] | Should -Be 42
    }

    It 'normalizes a one-element array without scalar collapse' {
        $view = ConvertTo-PnccCollectionView -InputObject @('only')
        $view.Count | Should -Be 1
        $view.Items.GetType().FullName | Should -Be 'System.Object[]'
        $view.Items[0] | Should -Be 'only'
    }

    It 'preserves a multi-item array and order' {
        $view = ConvertTo-PnccCollectionView -InputObject @('a', 'b', 'c')
        $view.Count | Should -Be 3
        $view.Items[0] | Should -Be 'a'
        $view.Items[2] | Should -Be 'c'
    }

    It 'treats a string as one logical item rather than characters' {
        $view = ConvertTo-PnccCollectionView -InputObject 'abc'
        $view.Count | Should -Be 1
        $view.Items[0] | Should -Be 'abc'
    }

    It 'treats a PSCustomObject as one logical item' {
        $item = [pscustomobject]@{ Name = 'one'; Value = 1 }
        $view = ConvertTo-PnccCollectionView -InputObject $item
        $view.Count | Should -Be 1
        $view.Items[0].Name | Should -Be 'one'
    }

    It 'stabilizes a zero-result Where-Object pipeline' {
        $raw = @(1, 2, 3) | Where-Object { $_ -gt 10 }
        $view = ConvertTo-PnccCollectionView -InputObject $raw
        $view.Count | Should -Be 0
        $view.IsEmpty | Should -BeTrue
    }

    It 'stabilizes a one-result Where-Object pipeline' {
        $raw = @(1, 2, 3) | Where-Object { $_ -eq 2 }
        $view = ConvertTo-PnccCollectionView -InputObject $raw
        $view.Count | Should -Be 1
        $view.Items[0] | Should -Be 2
    }

    It 'stabilizes an N-result Where-Object pipeline' {
        $raw = @(1, 2, 3) | Where-Object { $_ -ge 2 }
        $view = ConvertTo-PnccCollectionView -InputObject $raw
        $view.Count | Should -Be 2
        $view.Items[0] | Should -Be 2
        $view.Items[1] | Should -Be 3
    }
}
