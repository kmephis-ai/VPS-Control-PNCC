; PNCC canonical installer-definition proposal
; Windows 10 target intent
; PowerShell 5.1 compatibility required
; 127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY
; 127.0.0.1:1081 = PRIMARY_AUTO
; V6.3.1 immutable SHA-256 385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e
; PuTTY transport uses -pwfile only
; host-key verification is fail-closed and must remain enabled
; This definition copies canonical source files only. It does not launch PNCC during installation.

[Setup]
AppId={{7E95F644-7E60-4EBB-947C-4874087A561E}
AppName=VPS Control Center / PNCC
AppVersion=7.0.2
DefaultDirName={localappdata}\Programs\VPS-Control-PNCC
DefaultGroupName=VPS Control Center / PNCC
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputBaseFilename=VPS-Control-PNCC-v7.0.2-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=VPS Control Center / PNCC 7.0.2

[Files]
Source: "..\..\src\windows-v7\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs notimestamp

[Icons]
Name: "{group}\VPS Control Center"; Filename: "{app}\VPS-Control-v7.cmd"; WorkingDir: "{app}"
