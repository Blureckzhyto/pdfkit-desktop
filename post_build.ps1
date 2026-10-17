# Ancla dist\PDFKit\PDFKit.exe a la barra de tareas de Windows.
# Nota: en Windows 10/11 recientes Microsoft restringe el anclado programatico;
# si el verbo no esta disponible, se informa como anclarlo manualmente.

$dist = Join-Path $PSScriptRoot "dist\PDFKit"
$exe = Join-Path $dist "PDFKit.exe"

if (-not (Test-Path $exe)) {
    Write-Host "No se encontro $exe - ejecuta build.bat primero."
    exit 1
}

$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace($dist)
$item = $folder.ParseName("PDFKit.exe")

# Busca el verbo de anclado (nombre localizado: "Anclar a la barra de tareas" / "Pin to taskbar")
$verb = $item.Verbs() | Where-Object {
    ($_.Name -replace '&', '') -match 'barra de tareas|taskbar'
} | Select-Object -First 1

if ($verb) {
    $verb.DoIt()
    Write-Host "PDFKit.exe anclado a la barra de tareas."
} else {
    # Intento directo con el verbo canonico (funciona en versiones anteriores de Windows)
    $item.InvokeVerb("taskbarpin")
    Start-Sleep -Milliseconds 500
    Write-Host "Se intento anclar PDFKit.exe a la barra de tareas."
    Write-Host "Si no aparece anclado (Windows 10/11 lo restringe), haz clic derecho"
    Write-Host "sobre dist\PDFKit\PDFKit.exe y elige 'Anclar a la barra de tareas'."
}
