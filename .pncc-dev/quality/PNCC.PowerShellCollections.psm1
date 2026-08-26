Set-StrictMode -Version 3.0

function ConvertTo-PnccCollectionView {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [object]$InputObject
    )

    [object[]]$items = [object[]]@()
    if ($null -ne $InputObject) {
        $items = [object[]]@($InputObject)
    }

    [pscustomobject][ordered]@{
        SchemaVersion = 1
        Count = [int]$items.Count
        IsEmpty = ($items.Count -eq 0)
        Items = $items
    }
}

Export-ModuleMember -Function ConvertTo-PnccCollectionView
