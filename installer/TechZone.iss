; TechZone POS & Shop OS — Inno Setup 6 Installer Script
; Compiles dist\TechZone-Setup-v<Version>.exe for Windows 10/11 (x64)
; Requires dist\TechZone.exe built beforehand (via build-exe.bat or build-installer.bat)

#define MyAppName "TechZone POS"
#define MyAppFullName "TechZone POS & Shop OS"
#ifndef MyAppVersion
  #define MyAppVersion "2.0.0"
#endif
; تنظيف رقم الإصدار لـ VersionInfoVersion (إزالة حرف v البادئ أو لاحقة -beta/+build وحماية البناء على GitHub Actions)
#define MyAppVersionClean Trim(MyAppVersion)
#if Copy(MyAppVersionClean, 1, 1) == "v" || Copy(MyAppVersionClean, 1, 1) == "V"
  #define MyAppVersionClean Copy(MyAppVersionClean, 2)
#endif
#if Pos("-", MyAppVersionClean) > 0
  #define MyAppVersionClean Copy(MyAppVersionClean, 1, Pos("-", MyAppVersionClean) - 1)
#endif
#if Pos("+", MyAppVersionClean) > 0
  #define MyAppVersionClean Copy(MyAppVersionClean, 1, Pos("+", MyAppVersionClean) - 1)
#endif
#if MyAppVersionClean == "" || Copy(MyAppVersionClean, 1, 1) < "0" || Copy(MyAppVersionClean, 1, 1) > "9"
  #define MyAppVersionClean "2.0.0"
#endif
#define MyAppPublisher "Taqnia Technology - TechZone"
#define MyAppURL "https://github.com/hany-php/TechZone-POS"
#define MyAppExeName "TechZone.exe"

[Setup]
; Stable AppId GUID so newer releases cleanly upgrade in place without losing data
AppId={{8F4C7B2A-6E1D-4A93-B2C5-7D8E9A1F3B20}
AppName={#MyAppFullName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppFullName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
VersionInfoVersion={#MyAppVersionClean}
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppFullName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoDescription={#MyAppFullName} Windows Installer
DefaultDirName={autopf}\TechZone POS
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Lowest allows zero-UAC per-user install in %LocalAppData%\Programs\TechZone POS,
; while dialog option lets administrators install for all users if preferred.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=TechZone-Setup-v{#MyAppVersion}
SetupIconFile=..\icon.ico
Uninstallable=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppFullName}
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}
RestartApplications=yes
; إجبار ظهور نافذة اختيار اللغة (عربي / إنجليزي) في كل مرة يعمل فيها السطب
ShowLanguageDialog=yes
LanguageDetectionMethod=none
DisableWelcomePage=no

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
arabic.RunOnStartup=تشغيل البرنامج تلقائياً في شريط النظام بجوار الساعة عند بدء تشغيل ويندوز
english.RunOnStartup=Start automatically in the system tray when Windows starts
arabic.UninstallApp=إلغاء تثبيت {#MyAppName}
english.UninstallApp=Uninstall {#MyAppName}
arabic.WebView2Missing=لم يتم العثور على مكون Microsoft Edge WebView2 Runtime على هذا الجهاز. يعمل البرنامج بشكل مثالي على Windows 11، وقد يتطلب تثبيت WebView2 Runtime على بعض إصدارات Windows 10 القديمة.%n%nهل تريد المتابعة في التثبيت على أي حال؟
english.WebView2Missing=Microsoft Edge WebView2 Runtime was not detected on this machine. TechZone POS requires WebView2 Runtime (built into Windows 11 and modern Windows 10).%n%nDo you want to continue installation anyway?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:RunOnStartup}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
; Ensure data/, backups/, and receipts/ are writable even if installed system-wide
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\data\backups"; Permissions: users-modify
Name: "{app}\data\receipts"; Permissions: users-modify
Name: "{app}\data\images"; Permissions: users-modify
Name: "{app}\data\reports"; Permissions: users-modify
Name: "{app}\data\updates"; Permissions: users-modify

[Files]
Source: "..\dist\TechZone.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppFullName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autoprograms}\{cm:UninstallApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppFullName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppFullName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--tray"; IconFilename: "{app}\icon.ico"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppFullName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; حذف كافة الملفات والمجلدات الفرعية (قواعد البيانات، النسخ الاحتياطية، الفواتير) والمجلد الرئيسي
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}"

[Code]
function HasWebView2Key(RootKey: Integer; const SubKey: String): Boolean;
var
  Pv: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Pv) and (Pv <> '') and (Pv <> '0.0.0.0');
end;

function IsWebView2Installed(): Boolean;
begin
  Result :=
    HasWebView2Key(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') or
    HasWebView2Key(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') or
    HasWebView2Key(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}');
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not WizardSilent() then
  begin
    if not IsWebView2Installed() then
    begin
      if MsgBox(CustomMessage('WebView2Missing'), mbConfirmation, MB_YESNO) <> IDYES then
        Result := False;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDir := ExpandConstant('{app}');
    if DirExists(AppDir) then
      DelTree(AppDir, True, True, True);
  end;
end;