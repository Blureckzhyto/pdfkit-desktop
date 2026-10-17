; Instalador de PDFKit — compilar con Inno Setup 6:
;   ISCC.exe installer.iss
; Produce installer\PDFKit_Setup.exe

#define MyAppName "PDFKit"
#define MyAppVersion "1.3.7"
; Debe coincidir con ui/startup.py: une los accesos directos y la ventana en un solo botón de la barra de tareas
#define MyAppUserModelID "PDFKit.App"
#define MyAppPublisher "PDFKit"
#define MyAppExeName "PDFKit.exe"

[Setup]
; No cambiar el AppId entre versiones: identifica la app para el desinstalador
AppId={{7E64A9D1-52F3-4C08-B1A4-9D0E6C2F5B83}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Pide elevación para instalar en C:\Program Files\PDFKit
; (permite también instalación por usuario vía /CURRENTUSER o el diálogo)
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer
OutputBaseFilename=PDFKit_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Desde 1.3.7 la app es una carpeta (PDFKit.exe + _internal\): nada se extrae al abrirla.
; Al actualizar se borra la carpeta interna anterior para no dejar archivos viejos; el
; PDFKit.exe de 1.3.6 o anterior (un solo archivo) se reemplaza en el mismo lugar, así que
; los accesos directos y la entrada de "Agregar o quitar programas" (mismo AppId) siguen.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\Licencias"

[Files]
Source: "dist\PDFKit\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\PDFKit\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
; licencia AGPL-3.0 de PDFKit y licencias de todos los componentes de terceros
Source: "dist\PDFKit\Licencias\*"; DestDir: "{app}\Licencias"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
; lo que Python pueda haber creado dentro de la carpeta (cachés)
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
; Entrada en el menú Inicio
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; AppUserModelID: "{#MyAppUserModelID}"
; Acceso directo en el Escritorio (marcado por defecto)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; AppUserModelID: "{#MyAppUserModelID}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
