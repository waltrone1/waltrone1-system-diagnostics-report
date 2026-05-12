from __future__ import annotations

import ctypes
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote
import tkinter as tk
from tkinter import filedialog, ttk
import threading
from typing import Any, Callable


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(sys._MEIPASS)
else:
    APP_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = APP_DIR

OUTPUT_DIR = APP_DIR
JSON_OUTPUT = OUTPUT_DIR / "report_last.json"

APP_NAME = "waltrone1 System Diagnostics Report"
APP_VERSION = "1.0.0.0"
APP_BUILD_DATE = "2026-04-27"
APP_WEBSITE = "https://waltrone1.de/wltones-admin-tools/"
APP_CONTACT_EMAIL = "gwaltrone@gmail.com"
APP_PRODUCT = "waltrone1 Admin Tools"
APP_COMPANY = "waltrone1"
APP_TITLE = APP_NAME

from i18n import (
    CATEGORY_ORDER,
    CURRENT_LANG,
    DEFAULT_LANG,
    DISPLAY_LABELS,
    HEALTH_GROUPS,
    PHASE_TEXT,
    STATUS_LABELS,
    STATUS_LABELS_I18N,
    STATUS_PRIORITY,
    UI_TEXT,
    display_label,
    get_lang,
    localize_text,
    phase_mode_label,
    phase_tr,
    status_label,
    report_tr,
    tr,
    translate_category,
    translate_health_label,
    translate_title,
)


def is_windows() -> bool:
    return os.name == "nt"


def is_admin() -> bool:
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def now_str() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_spaces(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def build_google_search_url(query: str) -> str:
    normalized = _normalize_spaces(query)
    return f"https://www.google.com/search?q={quote(normalized)}" if normalized else "https://www.google.com/"


def build_ai_prompt_for_pattern(pattern: dict[str, Any]) -> str:
    title = _normalize_spaces(localize_text(pattern.get("title", "")))
    next_steps = [
        _normalize_spaces(localize_text(item))
        for item in ensure_list(pattern.get("next_steps", []))[:4]
        if _normalize_spaces(localize_text(item))
    ]
    related_modules = [
        _normalize_spaces(localize_text(item))
        for item in ensure_list(pattern.get("related_modules", []))[:5]
        if _normalize_spaces(localize_text(item))
    ]

    if CURRENT_LANG == "en":
        prompt_lines = [
            "I have a Windows diagnostic report and want additional possible causes and safe next-step solutions.",
            f"Diagnosis pattern: {title}",
            "Note: internal hostnames, domains, usernames and IP addresses are intentionally omitted.",
        ]
        if next_steps:
            prompt_lines.append("Recommended steps so far:")
            prompt_lines.extend(f"- {item}" for item in next_steps)
        if related_modules:
            prompt_lines.append("Relevant report modules:")
            prompt_lines.extend(f"- {item}" for item in related_modules)
        prompt_lines.extend([
            "Please answer in English.",
            "Please list additional possible root causes, prioritized validation steps and low-risk remediation options.",
            "Please point out which steps are suitable for a standard standalone PC and which are better suited for a domain-joined computer.",
        ])
        return "\n".join(prompt_lines)

    prompt_lines = [
        "Ich habe einen Windows-Diagnosebericht vorliegen und moechte weitere moegliche Ursachen und sichere Zusatzloesungen.",
        f"Diagnosemuster: {title}",
        "Hinweis: Es werden absichtlich keine internen Hostnamen, Domains, Benutzer oder IP-Adressen mitgegeben.",
    ]
    if next_steps:
        prompt_lines.append("Bisher empfohlene Schritte:")
        prompt_lines.extend(f"- {item}" for item in next_steps)
    if related_modules:
        prompt_lines.append("Betroffene Report-Module:")
        prompt_lines.extend(f"- {item}" for item in related_modules)
    prompt_lines.extend([
        "Bitte antworte auf Deutsch.",
        "Bitte nenne zusaetzliche moegliche Ursachen, priorisierte Pruefschritte und risikoarme Loesungswege.",
        "Bitte weise darauf hin, welche Schritte fuer einen normalen Einzelrechner und welche fuer einen Domaenenrechner sinnvoll sind.",
    ])
    return "\n".join(prompt_lines)


def build_external_research_links(pattern: dict[str, Any]) -> dict[str, str]:
    title = _normalize_spaces(localize_text(pattern.get("title", "")))
    related_modules = [
        _normalize_spaces(localize_text(item))
        for item in ensure_list(pattern.get("related_modules", []))[:3]
        if _normalize_spaces(localize_text(item))
    ]
    troubleshooting_term = "troubleshooting" if CURRENT_LANG == "en" else "Fehlerbehebung"
    search_query = " ".join(part for part in [title, "Windows", troubleshooting_term, " ".join(related_modules)] if part).strip()
    return {
        "google_url": build_google_search_url(search_query),
        "gemini_url": f"https://gemini.google.com/?hl={CURRENT_LANG}",
        "ai_prompt": build_ai_prompt_for_pattern(pattern),
    }


def powershell_json(script: str) -> Any:
    """
    Führt PowerShell aus und erwartet JSON auf stdout.
    Erzwingt UTF-8, damit Umlaute sauber an Python übergeben werden.
    Unter Windows wird das Konsolenfenster dabei versteckt.
    """
    wrapped_script = rf"""
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    {script}
    """

    creationflags = 0
    startupinfo = None

    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            wrapped_script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=creationflags,
        startupinfo=startupinfo,
    )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if completed.returncode != 0:
        raise RuntimeError(stderr or stdout or "PowerShell-Ausführung fehlgeschlagen.")

    if not stdout:
        return None

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ungültige JSON-Antwort aus PowerShell: {stdout[:500]}") from exc


def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{int(seconds * 1000)} ms"
    return f"{seconds:.2f} s"


def highest_status(statuses: list[str]) -> str:
    if not statuses:
        return "info"
    return max(statuses, key=lambda s: STATUS_PRIORITY.get(s, 0))


def make_result(
    module_id: str,
    title: str,
    category: str,
    priority: int,
    result_type: str,
    data: Any,
    status: str = "ok",
    summary: str = "",
    issues: list[str] | None = None,
    error: str | None = None,
    duration_ms: int = 0,
    description: str = "",
) -> dict[str, Any]:
    return {
        "id": module_id,
        "title": title,
        "category": category,
        "priority": priority,
        "status": status,
        "summary": summary,
        "description": description,
        "collected_at": now_str(),
        "duration_ms": duration_ms,
        "result_type": result_type,
        "data": data,
        "issues": issues or [],
        "error": error,
    }


CATEGORY_LABELS_I18N = {
    "de": {
        "Übersicht": "Übersicht",
        "Sicherheit": "Sicherheit",
        "Netzwerk": "Netzwerk",
        "Updates & Software": "Updates & Software",
        "Benutzer & Last": "Benutzer & Last",
        "Inventar & Tiefeninfos": "Inventar & Tiefeninfos",
    },
    "en": {
        "Übersicht": "Overview",
        "Sicherheit": "Security",
        "Netzwerk": "Network",
        "Updates & Software": "Updates & Software",
        "Benutzer & Last": "Users & Load",
        "Inventar & Tiefeninfos": "Inventory & Deep Details",
    },
}

HEALTH_LABELS_I18N = {
    "de": {
        "System": "System",
        "Sicherheit": "Sicherheit",
        "Netzwerk": "Netzwerk",
        "Updates": "Updates",
        "Sonstiges": "Sonstiges",
    },
    "en": {
        "System": "System",
        "Sicherheit": "Security",
        "Netzwerk": "Network",
        "Updates": "Updates",
        "Sonstiges": "Other",
    },
}

TITLE_LABELS_I18N = {
    "de": {},
    "en": {
        "Systeminfo": "System Information",
        "Systemprofil / Gerätetyp": "System Profile / Device Type",
        "Betriebssystem": "Operating System",
        "Windows-Aktivierung": "Windows Activation",
        "Join-Status": "Join Status",
        "Identität / Rechtekontext": "Identity / Rights Context",
        "Kerberos-Tickets": "Kerberos Tickets",
        "Arbeitsspeicher": "Memory",
        "Datenträger": "Drives",
        "Physische Datenträger / SMART / Medientyp": "Physical Disks / SMART / Media Type",
        "Hardware- / Geräte-IDs": "Hardware / Device IDs",
        "Hardware / Treiber-Basischeck": "Hardware / Driver Baseline Check",
        "Netzwerkadapter": "Network Adapters",
        "Externe Internet-IP": "External Internet IP",
        "Netzwerk vertiefen": "Network Deep Dive",
        "Routingtabelle": "Routing Table",
        "SMB-Mappings / Netzlaufwerke": "SMB Mappings / Network Drives",
        "DNS-Client-Cache": "DNS Client Cache",
        "Anmeldeinformationen (ohne Geheimnisse)": "Credential Inventory (without secrets)",
        "WLAN-Profile (ohne Schlüssel)": "Wi-Fi Profiles (without keys)",
        "Freigegebene Ordner / SMB-Basischeck": "Shared Folders / SMB Basic Check",
        "Remote-Zugriff": "Remote Access",
        "Zeitdienst / NTP": "Time Service / NTP",
        "Zertifikate": "Certificates",
        "BitLocker & TPM": "BitLocker & TPM",
        "Offene Ports": "Open Ports",
        "Neustartstatus": "Pending Reboot Status",
        "Verfügbare Windows-Updates": "Available Windows Updates",
        "Installierte Updates": "Installed Updates",
        "Freigegebene Ordner / SMB-Basischeck": "Shared Folders / SMB Basic Check",
        "Prozesse mit Diensten": "Processes with Services",
        "Geplante Tasks (Windows vs. eigene)": "Scheduled Tasks (Windows vs. Custom)",
        "Installierte Software": "Installed Software",
        "Installierte Updates": "Installed Updates",
        "Installierte Drucker": "Installed Printers",
        "Rollen / Features auf Servern": "Roles / Features on Servers",
        "DNS-/DHCP-Basischeck": "DNS / DHCP Basic Check",
        "AD-Server / DC-Basischeck": "AD Server / DC Basic Check",
        "IIS-Webserver-Basischeck": "IIS Web Server Basic Check",
        "Lokale Administratoren / privilegierte Gruppen": "Local Administrators / Privileged Groups",
        "Lokale Benutzer": "Local Users",
        "Aktive Benutzer": "Active Users",
        "Benutzerprofile unter C:\\Users": "User Profiles under C:\\Users",
        "Top-Prozesse": "Top Processes",
        "Prozesse mit Diensten": "Processes with Services",
        "Wichtige Dienste": "Important Services",
        "Geplante Tasks (Windows vs. eigene)": "Scheduled Tasks (Windows vs. Custom)",
        "Historie / Vergleich zum letzten Lauf": "History / Comparison with Previous Run",
        "Partitionen / Volumes": "Partitions / Volumes",
        "Eventlog-Kurzcheck": "Event Log Quick Check",
        "Historie / Vergleich zum letzten Lauf": "History / Comparison with Previous Run",
        "Verfügbare Updates": "Available Updates",
        "Reboot erforderlich": "Pending Reboot",
        "VSS-Writer": "VSS Writers",
        "Windows-Aktivierung": "Windows Activation",
        "Neustartstatus": "Reboot Status",
        "Lokale Benutzer": "Local Users",
        "Top-Prozesse": "Top Processes",
        "Defender-Signaturen": "Defender Signatures",
        "Antivirus-Schutz": "Antivirus Protection",
        "Remote-Zugriff": "Remote Access",
        "Zeitdienst / NTP": "Time Service / NTP",
        "Zertifikate": "Certificates",
        "Netzwerk vertiefen": "Network Deep Dive",
        "Wichtige Dienste": "Important Services",
    },
}

DISPLAY_LABELS_EN = {
    "QuerySuccess": "Query Successful",
    "QueryError": "Query Message",
    "HostName": "Host Name",
    "Buildnummer": "Build Number",
    "Architektur": "Architecture",
    "Abfrage erfolgreich": "Query Successful",
    "Hostname": "Host Name",
    "BIOS-Version": "BIOS Version",
    "Installationsdatum (systeminfo.exe)": "Install Date (systeminfo.exe)",
    "Installationsdatum (Fallback)": "Install Date (Fallback)",
    "Ursprüngliches Installationsdatum": "Original Install Date",
    "Quelle Installationsdatum": "Install Date Source",
    "Anmeldeserver": "Logon Server",
    "CredentialType": "Credential Type",
    "TargetName": "Target",
    "CredentialUser": "User",
    "IsGeneric": "Generic",
    "ProfileName": "Profile Name",
    "SSIDName": "SSID",
    "ConnectionMode": "Connection Mode",
    "ConnectionType": "Connection Type",
    "Authentication": "Authentication",
    "Encryption": "Encryption",
    "IsHidden": "Hidden",
    "AutoSwitch": "Auto Switch",
    "Domäne": "Domain",
    "Laufwerk": "Drive",
    "Auslastung_%": "Usage (%)",
    "Auslastung %": "Usage (%)",
    "Hersteller": "Manufacturer",
    "Letzter_Boot": "Last Boot",
    "Uptime_Tage": "Uptime Days",
    "BankLabel": "Bank Label",
    "Kapazität (GB)": "Capacity (GB)",
    "Takt (MHz)": "Speed (MHz)",
    "Teilenummer": "Part Number",
    "Produkttyp-ID": "Product Type ID",
    "Domänenrollen-ID": "Domain Role ID",
    "Entra-Geräte-ID": "Entra Device ID",
    "Monitore": "Monitors",
    "Zeitzonen-ID": "Time Zone ID",
    "Produkttyp-ID": "Product Type ID",
    "Domänenrollen-ID": "Domain Role ID",
    "Hersteller": "Manufacturer",
    "Benutzer": "User",
    "RDP-Port": "RDP Port",
    "Firewall": "Firewall",
    "Meldung": "Message",
    "Alle Listening-Ports": "All Listening Ports",
    "Angezeigte Ports": "Visible Ports",
    "Ausgeblendete Ports": "Hidden Ports",
    "Gängige Ports": "Common Ports",
    "Netzmaske": "Subnet Mask",
    "Zeit": "Time",
    "Pfad": "Path",
    "Zielnetz": "Destination Prefix",
    "Gateway": "Gateway",
    "Metrik": "Metric",
    "Manufacturer": "Manufacturer",
    "UserName": "User",
    "TimeZoneId": "Time Zone ID",
    "DisplayName": "Display Name",
    "Rolle": "Role",
    "Erwartet": "Expected",
    "Bewertung": "Assessment",
    "Empfehlung": "Recommendation",
    "Hinweis": "Note",
    "valid_until": "Valid Until",
    "days_remaining": "Days Remaining",
    "ServiceStatus": "Service Status",
    "StartType": "Start Type",
    "RealTimeProtectionEnabled": "Real-Time Protection",
    "AntivirusEnabled": "Antivirus Enabled",
    "LocalAddress": "Local Address",
    "Port_Beschreibung": "Service",
    "OwningProcess": "Process ID",
    "ProcessName": "Process",
    "LogName": "Log",
    "ProviderName": "Source",
    "Message": "Message",
    "PartNumber": "Part Number",
    "Capacity_GB": "Capacity (GB)",
    "Speed_MHz": "Speed (MHz)",
    "InterfaceAlias": "Interface Alias",
    "Quelle": "Source",
    "Laufwerk": "Drive",
    "Prozess": "Process",
    "Prozess-ID": "Process ID",
    "StartType": "Start Type",
    "Antivirus aktiv": "Antivirus Enabled",
    "Echtzeitschutz": "Real-Time Protection",
    "Dienststatus": "Service Status",
    "Starttyp": "Start Type",
    "Aktiviert": "Enabled",
    "Lizenziert": "Licensed",
    "TPM-Version": "TPM Version",
    "TPM-Spezifikation": "TPM Specification",
    "Produktname": "Display Name",
    "Antivirus aktiv": "Antivirus Enabled",
    "Echtzeitschutz": "Real-Time Protection",
    "Dienststatus": "Service Status",
    "Starttyp": "Start Type",
    "Drucker": "Printers",
    "Serverrollen": "Server Roles",
    "Kapazität (GB)": "Capacity (GB)",
    "Takt (MHz)": "Speed (MHz)",
    "Teilenummer": "Part Number",
    "Aktiviert": "Enabled",
    "Dienststatus": "Service Status",
    "Starttyp": "Start Type",
    "Produktname": "Product Name",
    "RDP-Port": "RDP Port",
    "Firewall": "Firewall",
    "Meldung": "Message",
    "Alle Listening-Ports": "All Listening Ports",
    "Angezeigte Ports": "Visible Ports",
    "Ausgeblendete Ports": "Hidden Ports",
    "Gängige Ports": "Common Ports",
    "Netzmaske": "Subnet Mask",
    "Zeit": "Time",
    "Pfad": "Path",
    "Zielnetz": "Destination Prefix",
    "Gateway": "Gateway",
    "Metrik": "Metric",
    "Manufacturer": "Manufacturer",
    "UserName": "User",
    "TimeZoneId": "Time Zone ID",
    "DisplayName": "Product Name",
    "ServiceStatus": "Service Status",
    "StartType": "Start Type",
    "RealTimeProtectionEnabled": "Real-Time Protection",
    "AntivirusEnabled": "Antivirus Enabled",
    "LocalAddress": "Local Address",
    "Port_Beschreibung": "Service",
    "OwningProcess": "Process ID",
    "ProcessName": "Process",
    "LogName": "Log",
    "ProviderName": "Source",
    "Message": "Message",
    "PartNumber": "Part Number",
    "Capacity_GB": "Capacity (GB)",
    "Speed_MHz": "Speed (MHz)",
    "InterfaceAlias": "Interface Alias",
    "Quelle": "Source",
    "Laufwerk": "Drive",
    "Prozess": "Process",
    "Prozess-ID": "Process ID",
    "StartType": "Start Type",
    "Zeitzonen-ID": "Time Zone ID",
    "Produkttyp-ID": "Product Type ID",
    "Domänenrollen-ID": "Domain Role ID",
    "Hersteller": "Manufacturer",
    "Benutzer": "User",
    "RDP-Port": "RDP Port",
    "Firewall": "Firewall",
    "Meldung": "Message",
    "Alle Listening-Ports": "All Listening Ports",
    "Angezeigte Ports": "Visible Ports",
    "Ausgeblendete Ports": "Hidden Ports",
    "Gängige Ports": "Common Ports",
    "Netzmaske": "Subnet Mask",
    "Zeit": "Time",
    "Pfad": "Path",
    "Zielnetz": "Destination Prefix",
    "Gateway": "Gateway",
    "Metrik": "Metric",
    "Manufacturer": "Manufacturer",
    "UserName": "User",
    "TimeZoneId": "Time Zone ID",
    "DisplayName": "Product Name",
    "ServiceStatus": "Service Status",
    "StartType": "Start Type",
    "RealTimeProtectionEnabled": "Real-Time Protection",
    "AntivirusEnabled": "Antivirus Enabled",
    "LocalAddress": "Local Address",
    "Port_Beschreibung": "Service",
    "OwningProcess": "Process ID",
    "ProcessName": "Process",
    "LogName": "Log",
    "ProviderName": "Source",
    "Message": "Message",
    "PartNumber": "Part Number",
    "Capacity_GB": "Capacity (GB)",
    "Speed_MHz": "Speed (MHz)",
    "InterfaceAlias": "Interface Alias",
    "Quelle": "Source",
    "Laufwerk": "Drive",
    "Prozess": "Process",
    "Prozess-ID": "Process ID",
    "StartType": "Start Type",
    "Antivirus aktiv": "Antivirus Enabled",
    "Echtzeitschutz": "Real-Time Protection",
    "Dienststatus": "Service Status",
    "Starttyp": "Start Type",
    "Aktiviert": "Enabled",
    "Lizenziert": "Licensed",
    "Gerätename": "Device Name",
    "Benutzer": "User",
    "Gesamt_GB": "Total (GB)",
    "Frei_GB": "Free (GB)",
    "Belegt_GB": "Used (GB)",
    "Auslastung_Prozent": "Usage (%)",
    "RAM_Module_Belegt": "Installed Modules",
    "RAM_Slots_Gesamt": "Total Slots",
    "RAM_Slots_Frei": "Free Slots",
    "RAM_Module_Details": "RAM Modules",
    "Beschreibung": "Description",
    "Installiert_am": "Installed On",
    "MountPoint": "Drive",
    "ProtectionStatus": "Protection Status",
    "EncryptionMethod": "Encryption",
    "KeyProtectorTypes": "Protection Methods",
    "TpmPresent": "TPM Present",
    "TpmReady": "TPM Ready",
    "TpmEnabled": "TPM Enabled",
    "TpmActivated": "TPM Activated",
    "Primärer_Schutz": "Primary Protection",
    "Drittanbieter_Produkte": "Third-Party Products",
    "Defender_Status": "Defender Status",
    "IPs": "IP Addresses",
    "DNS_Server": "DNS Servers",
    "Reboot_Required": "Reboot Status",
    "Reason_Count": "Reason Count",
    "Reasons": "Detected Reasons",
    "Details": "Details",
    "ComputerName_Aktiv": "Active Computer Name",
    "ComputerName_Konfiguriert": "Configured Computer Name",
    "ComputerName_Aenderung_Ausstehend": "Computer Name Change Pending",
    "Available_Update_Count": "Available Updates",
    "Security_Update_Count": "Security Updates",
    "Regular_Update_Count": "Regular Updates",
    "Definition_Update_Count": "Definition Updates",
    "Driver_Update_Count": "Driver Updates",
    "Optional_Update_Count": "Optional / Preview Updates",
    "RebootLikely_Update_Count": "Updates with Possible Reboot",
    "QuerySuccess": "Query Successful",
    "QueryError": "Query Message",
    "KB": "KB",
    "Categories": "Categories",
    "Severity": "Severity",
    "RebootBehavior": "Reboot Behavior",
    "Downloaded": "Downloaded",
    "BrowseOnly": "Optional / Manual",
    "Updates": "Updates",
    "Latest_InstallDate": "Latest Installed Update",
    "Installed_Last_30_Days": "Installed Updates (30 Days)",
    "Installed_Last_90_Days": "Installed Updates (90 Days)",
    "Update_Age_Days": "Age of Latest Update (Days)",
    "Installed_Software_Count": "Installed Software",
    "x64_Count": "64-bit Entries",
    "x86_Count": "32-bit Entries",
    "Software": "Software",
    "Publisher": "Publisher",
    "InstallDate": "Install Date",
    "EstimatedSizeMB": "Size (MB)",
    "InstallLocation": "Install Path",
    "Architecture": "Architecture",
    "RegistryHive": "Registry View",
    "ProductCode": "GUID / ProductCode",
    "GUID_Count": "Entries with GUID",
    "ProductName": "Product",
    "Activation_Status": "Activation Status",
    "IsActivated": "Activated",
    "LicenseDescription": "License Description",
    "LicenseChannel": "License Channel",
    "PartialProductKey": "Partial Product Key",
    "GracePeriodRemaining_Minutes": "Remaining Grace Period (Min.)",
    "GracePeriodRemaining_Days": "Remaining Grace Period (Days)",
    "PartOfDomain": "Domain Joined",
    "DomainRoleText": "System Role",
    "Workgroup": "Workgroup",
    "TenantName": "Tenant",
    "DsregcmdAvailable": "dsregcmd Available",
    "RDP_Enabled": "RDP Enabled",
    "NLA_Required": "NLA Required",
    "WinRM_ServiceStatus": "WinRM Service Status",
    "WinRM_StartType": "WinRM Start Type",
    "WinRM_ListenerCount": "WinRM Listeners",
    "PSRemotingAvailable": "PowerShell Remoting Available",
    "DefenderAvailable": "Defender Cmdlets Available",
    "AntivirusSignatureVersion": "AV Signature Version",
    "AntivirusSignatureLastUpdated": "AV Signatures Last Updated",
    "SignatureAgeDays": "Signature Age (Days)",
    "AMEngineVersion": "Defender Engine Version",
    "NISSignatureVersion": "NIS Signature Version",
    "NISSignatureLastUpdated": "NIS Signatures Last Updated",
    "NISSignatureAgeDays": "NIS Signature Age (Days)",
    "W32Time_ServiceStatus": "Time Service Status",
    "W32Time_StartType": "Time Service Start Type",
    "TimeServiceType": "Time Source Type",
    "NtpServer": "NTP Server",
    "TimeSource": "Current Time Source",
    "TimeZoneName": "Time Zone",
    "TimeSourceError": "Time Source Query Note",
    "QueryMode": "Query Mode",
    "Disk_Count": "Physical Disks",
    "SSD_Count": "SSD Count",
    "HDD_Count": "HDD Count",
    "Unknown_Media_Count": "Unknown Media Types",
    "Disks": "Disks",
    "Index": "Index",
    "Model": "Model",
    "SerialNumber": "Serial Number",
    "MediaType": "Media Type",
    "BusType": "Bus Type",
    "HealthStatus": "Health Status",
    "OperationalStatus": "Operational Status",
    "Size_GB": "Size (GB)",
    "Temperature_C": "Temperature (°C)",
    "PredictFailure": "SMART Failure Prediction",
    "PowerOnHours": "Power-On Hours",
    "Share_Count_Total": "Total Shares",
    "Share_Count_Visible": "Visible Shares",
    "AdminShare_Count": "Hidden Admin Shares",
    "Risky_Share_Count": "Suspicious Shares",
    "Shares": "Shares",
    "ShareName": "Share Name",
    "ShareType": "Share Type",
    "AccessSummary": "Permissions",
    "RiskyAccess": "Suspicious Permission",
    "Auffaelligkeit": "Finding",
    "Administrators_Count": "Local Administrators",
    "RemoteDesktopUsers_Count": "Remote Desktop Users",
    "Benutzer": "User",
    "TaskName": "Task Name",
    "Services": "Services",
    "LogonId": "Logon ID",
    "BackupOperators_Count": "Backup Operators",
    "Administrators": "Local Administrators",
    "RemoteDesktopUsers": "Remote Desktop Users",
    "BackupOperators": "Backup Operators",
    "ObjectClass": "Object Class",
    "Source": "Source",
    "ADSPath": "ADS Path",
    "Suspicious_Task_Count": "Suspicious Tasks Total",
    "Windows_Task_Count": "Suspicious Windows Tasks",
    "Windows_Failed_Task_Count": "Windows Tasks with Error Status",
    "Custom_Task_Count": "Suspicious Custom / Third-Party Tasks",
    "Custom_Failed_Task_Count": "Custom / Third-Party Tasks with Error Status",
    "Disabled_Custom_Task_Count": "Disabled Custom / Third-Party Tasks",
    "Tasks": "Scheduled Tasks",
    "TaskPath": "Task Path",
    "Enabled": "Enabled",
    "LastRunTime": "Last Run",
    "NextRunTime": "Next Run",
    "LastTaskResult": "Last Result",
    "ResultText": "Result Text",
    "IssueType": "Finding",
    "IsMicrosoftTask": "Windows Task",
    "SystemType": "System Type",
    "IsServer": "Server System",
    "ProductTypeText": "Product Type",
    "SystemProfile": "System Profile",
    "InstalledRoleCount": "Detected Roles / Features",
    "InstalledRoles": "Installed Roles / Features",
    "Group": "Group",
    "InstallState": "Install State",
    "Device_Count": "Total Devices",
    "Problem_Device_Count": "Devices with Issues",
    "Generic_Driver_Count": "Generic Drivers",
    "Critical_Class_Problem_Count": "Important Problem Devices",
    "Devices": "Devices",
    "DeviceName": "Device Name",
    "DeviceClass": "Device Class",
    "DriverProviderName": "Driver Provider",
    "DriverVersion": "Driver Version",
    "DriverDate": "Driver Date",
    "ConfigManagerErrorCode": "Code",
    "Adapter_Count": "Total Adapters",
    "Multi_Gateway_Detected": "Multiple Gateways Detected",
    "Apipa_Count": "APIPA Adapters",
    "Missing_Dns_Count": "Adapters without DNS",
    "Disconnected_Count": "Inactive Adapters",
    "Adapters": "Adapters",
    "InterfaceDescription": "Adapter Description",
    "LinkSpeed": "Link Speed",
    "MacAddress": "MAC Address",
    "VirtualAdapter": "Virtual Adapter",
    "HardwareInterface": "Physical Adapter",
    "DefaultGateway": "Default Gateway",
    "DnsServers": "DNS Servers",
    "ApipaDetected": "APIPA Detected",
    "ServerRole": "Server Role",
    "DNS_Installed": "DNS Installed",
    "DNS_ServiceStatus": "DNS Service Status",
    "DNS_ZoneCount": "DNS Zones",
    "DHCP_Installed": "DHCP Installed",
    "DHCP_ServiceStatus": "DHCP Service Status",
    "DHCP_ScopeCount": "DHCP Scopes",
    "DHCP_Authorized": "DHCP Authorized",
    "IsDomainController": "Domain Controller",
    "Dc_Service_Count": "DC Services",
    "Dc_Share_Count": "DC Shares",
    "DcServices": "DC Services",
    "DcShares": "DC Shares",
    "Present": "Present",
    "IIS_Installed": "IIS Installed",
    "W3SVC_Status": "W3SVC Status",
    "Site_Count": "Sites",
    "AppPool_Count": "App Pools",
    "Sites": "Sites",
    "AppPools": "App Pools",
    "PhysicalPath": "Path",
    "BindingInfo": "Bindings",
    "HttpsBindingCount": "HTTPS Bindings",
    "Previous_Report_Found": "Previous Report Found",
    "Previous_Generated_At": "Previous Run",
    "New_Warning_Modules": "New Warnings / Critical",
    "Resolved_Warning_Modules": "Resolved Warnings / Critical",
    "New_Software": "New Software",
    "New_Visible_Ports": "New Relevant Ports",
    "New_Shares": "New Shares",
    "ComputerName": "Computer Name",
    "FQDN": "FQDN",
    "LocalDeviceId": "MachineGuid (local)",
    "WindowsProductId": "Windows Product ID",
    "HostName": "Host Name",
    "BiosVersion": "BIOS Version",
    "DomainInfo": "Domain",
    "OriginalInstallDate": "Original Install Date",
    "LogonServer": "Logon Server",
    "ExternalIP": "External IP Address",
    "ServiceUsed": "Queried Service",
    "ComputerScopeSuccess": "Computer Scope Successful",
    "ComputerScopeError": "Computer Scope Notes",
    "ComputerScopeText": "Computer Scope",
    "UserScopeSuccess": "User Scope Successful",
    "UserScopeError": "User Scope Notes",
    "UserScopeText": "User Scope",
    "Printer_Count": "Total Printers",
    "Shared_Count": "Shared Printers",
    "Offline_Count": "Offline Printers",
    "Default_Count": "Default Printers",
    "Printers": "Printers",
    "DriverName": "Driver Name",
    "PortName": "Port",
    "Shared": "Shared",
    "Default": "Default",
    "WorkOffline": "Offline",
    "PrinterStatus": "Printer Status",
    "Profile_BasePath": "Profile Base Path",
    "Profile_Count": "Total Profile Folders",
    "Custom_Profile_Count": "User Profiles",
    "OrphanLike_Count": "Suspicious Profile Folders",
    "Profiles": "Profile Folders",
    "ProfileName": "Profile Name",
    "FullPath": "Full Path",
    "IsDefaultProfile": "Default/System Profile",
    "NtUserDatExists": "NTUSER.DAT Present",
    "LastWriteTime": "Last Modified",
    "Hardware_UUID": "Hardware UUID",
    "Bios_ID": "BIOS ID",
    "Firmware_IDs": "Firmware IDs",
    "CPU_IDs": "CPU IDs",
    "Mainboard_ID": "Mainboard ID",
    "Network_IDs": "Network IDs",
    "Windows_IDs": "Windows System IDs",
    "Storage_WWN": "Storage WWN / PhysicalDisk",
    "Storage_IDs": "Storage IDs / DiskDrive",
    "GPU_IDs": "GPU IDs",
    "TPM_Info": "TPM Info",
    "RAM_Serials": "RAM Serials",
    "Monitor_IDs": "Monitor IDs (EDID)",
    "USB_Device_IDs": "USB Device IDs",
    "PCI_Device_IDs": "PCI Device IDs",
    "Sound_Device_IDs": "Sound Device IDs",
    "Bluetooth_Device_IDs": "Bluetooth Adapter IDs",
    "Battery_Info": "Battery Info",
    "Chassis_Info": "Chassis Info",
    "NVMe_Storage_IDs": "NVMe Specific IDs",
    "CollectionErrors": "Partial Errors",
    "OriginalInstallDate_SystemInfo": "Install Date (systeminfo.exe)",
    "OriginalInstallDate_Fallback": "Install Date (Fallback)",
    "InstallDateSource": "Install Date Source",
    "LocalDateTime": "Local Time",
    "UtcDateTime": "UTC Time",
    "TimeZoneOffset": "UTC Offset",
}

PHRASE_REPLACEMENTS_EN = [
    ("Administrator-Rechte erkannt.", "Administrator rights detected."),
    ("Zusammenfassung und Basisinformationen zu", "Summary and baseline information about"),
    ("Sicherheitsbezogene Informationen und Bewertung zu", "Security-related information and assessment for"),
    ("Netzwerkbezogene Informationen und Details zu", "Network-related information and details for"),
    ("Informationen zu Updates, Software und Status von", "Information about updates, software and status of"),
    ("Benutzer-, Prozess- oder Auslastungsinformationen zu", "User, process or load information for"),
    ("Vertiefte System- und Inventarinformationen zu", "Detailed system and inventory information for"),
    ("Zusätzliche Informationen zu", "Additional information about"),
    ("Keine Daten vorhanden.", "No data available."),
    ("Keine Laufwerksdaten verfügbar", "No drive data available"),
    ("Nicht verfügbar", "Not available"),
    ("Unbekannt", "Unknown"),
    ("Keine relevanten Zertifikate gefunden", "No relevant certificates found"),
    ("Dienst", "Service"),
    ("Zertifikat", "Certificate"),
    ("Automatisch", "Automatic"),
    ("Automatisch (wenn vorhanden)", "Automatic (if present)"),
    ("Manuell oder Automatisch", "Manual or Automatic"),
    ("Kritisch", "Critical"),
    ("Warnung", "Warning"),
    ("Hinweis", "Info"),
    ("Keine Aktion erforderlich", "No action required"),
    ("Starttyp auf Automatisch stellen und Dienststart prüfen", "Set the start type to Automatic and verify service startup"),
    ("Starttyp auf Automatisch anpassen", "Adjust the start type to Automatic"),
    ("Dienst starten und abhängige Fehler prüfen", "Start the service and review dependent errors"),
    ("Dienst prüfen oder Windows-Komponente reparieren", "Review the service or repair the Windows component"),
    ("Nur relevant, wenn die zugehörige Serverrolle genutzt wird", "Only relevant when the corresponding server role is used"),
    ("Deaktivierten Dienst nur bei bewusster Härtung beibehalten; sonst Starttyp prüfen", "Keep the service disabled only for intentional hardening; otherwise review the start type"),
    ("abgelaufen", "expired"),
    ("bald ablaufend", "expiring soon"),
    ("Keine Kerberos-Tickets gefunden", "No Kerberos tickets found"),
    ("Kein Domain Join", "No domain join"),
    ("Domäne", "Domain"),
    ("Lizenziert", "Licensed"),
    ("Primärer Schutz", "Primary protection"),
    ("Defender-Dienst", "Defender service"),
    ("gängigige", "common"),
    ("gängige Listening-Port(s) sichtbar", "common listening port(s) visible"),
    ("sonstige ausgeblendet", "other ports hidden"),
    ("Neustarthinweis vorhanden", "Reboot note present"),
    ("Ausstehende Datei-/Temp-Bereinigung erkannt", "Pending file/temp cleanup detected"),
    ("Datei-/Treiber-Operationen warten auf Neustart", "File/driver operations are waiting for a restart"),
    ("Sicherheitsupdate(s) verfügbar", "security update(s) available"),
    ("Update(s) können einen Neustart erfordern", "update(s) may require a restart"),
    ("reguläre Update(s) verfügbar", "regular update(s) available"),
    ("Definitionsupdate(s) verfügbar", "definition update(s) available"),
    ("Treiberupdate(s) verfügbar", "driver update(s) available"),
    ("optionale/Vorschau-Update(s) verfügbar", "optional/preview update(s) available"),
    ("Eintrag/Einträge", "entries"),
    ("Zuletzt installiert", "Last installed"),
    ("Client-System erkannt", "Client system detected"),
    ("hier nicht relevant", "not relevant here"),
    ("auf diesem Gerät nicht relevant", "not relevant on this device"),
    ("Domain Controller erkannt", "Domain controller detected"),
    ("Lokale Administratoren", "Local Administrators"),
    ("RDP-Benutzer", "RDP Users"),
    ("Backup Operators", "Backup Operators"),
    ("aktive Sitzung(en)", "active session(s)"),
    ("Top 5 nach CPU und RAM", "Top 5 by CPU and RAM"),
    ("Wichtige Windows-Dienste geprüft", "Important Windows services checked"),
    ("Keine auffälligen geplanten Tasks erkannt", "No suspicious scheduled tasks detected"),
    ("Geplante Tasks konnten nicht geprüft werden", "Scheduled tasks could not be checked"),
    ("installierte Update(s) gefunden", "installed update(s) found"),
    ("letztes Datum unklar", "latest date unclear"),
    ("Laufwerk(e) geprüft", "drive(s) checked"),
    ("physische Datenträger", "physical disks"),
    ("Erweiterte Datenträgerdaten wurden über WMI-Fallback ermittelt.", "Extended disk data was gathered via WMI fallback."),
    ("Gesundheitsstatus/SMART-Daten sind auf diesem System nicht vollständig verfügbar.", "Health status / SMART data is not fully available on this system."),
    ("Freigaben konnten nicht ermittelt werden", "Shares could not be determined"),
    ("sichtbare Freigabe(n)", "visible share(s)"),
    ("Admin-Freigaben ausgeblendet", "admin shares hidden"),
    ("Keine benutzerdefinierten Freigaben sichtbar", "No custom shares visible"),
    ("Zeitdienst aktiv", "Time service active"),
    ("Quelle nicht lesbar", "source not readable"),
    ("Quelle unklar", "source unclear"),
    ("Zeitquelle", "Time source"),
    ("System läuft seit mehr als 45 Tagen ohne Neustart.", "System has been running for more than 45 days without reboot."),
    ("RAM-Auslastung kritisch", "RAM usage critical"),
    ("RAM-Auslastung erhöht", "RAM usage elevated"),
    ("ist kritisch belegt", "is critically full"),
    ("ist hoch belegt", "is highly utilized"),
    ("Neue Warnungen/Kritisch", "New warnings / critical"),
    ("Behobene Warnungen/Kritisch", "Resolved warnings / critical"),
    ("Vergleich zum vorherigem Lauf", "Comparison with previous run"),
    ("keine relevanten Änderungen", "no relevant changes"),
    ("aktive/r Adapter ohne DNS-Server-Eintrag", "active adapter(s) without DNS server entry"),
    ("Geplante Tasks", "Scheduled Tasks"),
    ("auffällige Windows-Task(s) nur als Hinweis erfasst.", "suspicious Windows task(s) recorded as informational only."),
    ("eigene / Drittanbieter-Task(s) mit Fehlerstatus erkannt.", "custom / third-party task(s) with error status detected."),
    ("Erstellt", "Created"),
    ("Dauer", "Duration"),
    ("Quelle: systeminfo.exe", "Source: systeminfo.exe"),
    ("Installiert:", "Installed:"),
    ("Abfrage erfolgreich", "Query successful"),
    ("BIOS-Version", "BIOS Version"),
    ("Installationsdatum", "Install date"),
    ("Quelle Installationsdatum", "Install date source"),
    ("Anmeldeserver", "Logon server"),
    ("Betriebssystem", "Operating system"),
    ("Arbeitsspeicher", "Memory"),
    ("Datenträger", "Drives"),
    ("Netzwerkadapter", "Network Adapters"),
    ("Lokale Administratoren / privilegierte Gruppen", "Local administrators / privileged groups"),
    ("Freigegebene Ordner / SMB-Basischeck", "Shared folders / SMB basic check"),
    ("Offene Ports", "Open ports"),
    ("Geplante Tasks (Windows vs. eigene)", "Scheduled tasks (Windows vs. custom)"),
    ("Verfügbare Windows-Updates", "Available Windows updates"),
    ("Historie / Vergleich zum letzten Lauf", "History / comparison with previous run"),
    ("Kein vorheriger Report für Vergleich vorhanden", "No previous report available for comparison"),
    ("VSS-Writer erfordern Administratorrechte", "VSS writers require administrator rights"),
    ("Partition(en) über alle Datenträger", "partition(s) across all disks"),
    ("physische Datenträger", "physical disks"),
    ("belegt | Module", "used | modules"),
    ("aktive Privilegien", "active privileges"),
    ("Kernbereiche", "Core areas"),
    ("Gerätefehler", "Device errors"),
    ("Adapter aktiv", "adapters active"),
    ("fehlendes DNS", "missing DNS"),
    ("Netzlaufwerk(e)", "network drive(s)"),
    ("DNS-Cache-Einträge angezeigt", "DNS cache entries shown"),
    ("benutzerdefinierte Freigabe(n)", "custom share(s)"),
    ("RDP aktiv mit NLA", "RDP active with NLA"),
    ("Lokal:", "Local:"),
    ("Typ:", "Type:"),
    ("BitLocker- und TPM-Status geprüft", "BitLocker and TPM status checked"),
    ("Sicherheit:", "Security:"),
    ("Regulär:", "Regular:"),
    ("30 Tage", "30 days"),
    ("Freigegeben", "Shared"),
    ("lokale Benutzer | aktiv", "local users | active"),
    ("Benutzerprofil(e) | gesamt", "user profile(s) | total"),
    ("Prozess(e) hosten Windows-Dienste", "process(es) host Windows services"),
    ("Vorheriger Report gefunden", "Previous report found"),
    ("Vorheriger Lauf", "Previous run"),
    ("Neue Warnungen/Kritisch", "New warnings / critical"),
    ("Behobene Warnungen/Kritisch", "Resolved warnings / critical"),
    ("Neue Software", "New software"),
    ("Neue relevante Ports", "New relevant ports"),
    ("Neue Freigaben", "New shares"),
    ("Zusammenfassung und Basisinformationen zu", "Summary and baseline information about"),
    ("Vertiefte System- und Inventarinformationen zu", "Detailed system and inventory information for"),
    ("Fehler beim Aufrufen der Methode", "Error calling method"),
    ("Keine Methode mit dem Namen", "No method named"),
    ("Admin Checklist Fehlersuche", "Admin Troubleshooting Checklist"),
    ("Admin Checklist schließen", "Close admin checklist"),
    ("Netzwerkadapter", "Network Adapters"),
    ("Remote-Zugriff", "Remote Access"),
    ("Eventlog-Kurzcheck", "Event Log Quick Check"),
    ("Zeitdienst / NTP", "Time Service / NTP"),
    ("Join-Status", "Join Status"),
    ("Zertifikate", "Certificates"),
    ("DNS-/DHCP-Basischeck", "DNS / DHCP Basic Check"),
    ("Wichtige Dienste", "Important Services"),
    ("Freigegebene Ordner / SMB-Basischeck", "Shared Folders / SMB Basic Check"),
    ("Lokale Administratoren", "Local Administrators"),
    ("Offene Ports", "Open Ports"),
    ("Datenträger", "Drives"),
    ("Reboot erforderlich", "Pending Reboot"),
    ("Verfügbare Updates", "Available Updates"),
    ("Antivirus-Schutz", "Antivirus Protection"),
    ("Defender-Signaturen", "Defender Signatures"),
    ("Top-Prozesse", "Top Processes"),
    ("Geplante Tasks", "Scheduled Tasks"),
    ("Lokale Benutzerkonten mit Status und letzter Anmeldung.", "Local user accounts with status and last sign-in."),
    ("Information about updates, software and status of windows-aktivierung.", "Information about updates, software and status of Windows activation."),
    ("Information about updates, software and status of neustartstatus.", "Information about updates, software and status of reboot status."),
    ("Detailed system and inventory information for eventlog-kurzcheck.", "Detailed system and inventory information for event log quick check."),
    ("Keine relevanten Zertifikate gefunden", "No relevant certificates found"),
    ("Donnerstag", "Thursday"),
    ("Freitag", "Friday"),
    ("Samstag", "Saturday"),
    ("Sonntag", "Sunday"),
    ("Montag", "Monday"),
    ("Dienstag", "Tuesday"),
    ("Mittwoch", "Wednesday"),
    ("Januar", "January"),
    ("Februar", "February"),
    ("März", "March"),
    ("April", "April"),
    ("Mai", "May"),
    ("Juni", "June"),
    ("Juli", "July"),
    ("August", "August"),
    ("September", "September"),
    ("Oktober", "October"),
    ("November", "November"),
    ("Dezember", "December"),
    ("Nein", "No"),
    ("Ja", "Yes"),
    ("Gruppen:", "Groups:"),
    ("Monitore:", "Monitors:"),
    ("generische Treiber", "generic drivers"),
    ("Adapter", "adapters"),
    ("IPv4-Routen", "IPv4 routes"),
    ("Default-Routen", "default routes"),
    ("Drucker", "printers"),
    ("Serverrollen", "server roles"),
    ("DNS-/DHCP-Serverrollen", "DNS/DHCP server roles"),
    ("DC-Basischeck", "DC basic check"),
    ("IIS-Basischeck", "IIS basic check"),
    ("Eigene auffällig", "Custom suspicious"),
    ("Fehler:", "Errors:"),
    ("Deaktiviert:", "Disabled:"),
    ("Windows-Hinweise", "Windows notices"),
    ("gpresult für Computer- und Benutzerkontext gelesen", "gpresult read for computer and user context"),
    ("Event(s) aus System/Application der letzten 3 Tage", "event(s) from System/Application in the last 3 days"),
    ("Defender-Signaturen", "Defender signatures"),
    ("Tage alt", "days old"),
    ("Update(s) verfügbar", "update(s) available"),
    ("Tage:", "Days:"),
    ("RDP aktiv mit NLA", "RDP active with NLA"),
    ("Time source konnte nicht direkt abgefragt werden", "Time source could not be queried directly"),
    ("Folgender Fehler ist aufgetreten:", "The following error occurred:"),
    ("Zugriff verweigert", "Access denied"),
    ("Verbundene Netzlaufwerke und ihre aktuellen SMB-Zielpfade.", "Connected network drives and their current SMB target paths."),
    ("Aktueller Benutzer, Gruppen und wirksame Rechte dieses Prozesses.", "Current user, groups and effective rights of this process."),
    ("Summary and baseline information about systeminfo.", "Summary and baseline information about system information."),
    ("Summary and baseline information about betriebssystem.", "Summary and baseline information about operating system."),
    ("Summary and baseline information about systemprofil / gerätetyp.", "Summary and baseline information about system profile / device type."),
    ("Summary and baseline information about join-status.", "Summary and baseline information about join status."),
    ("Summary and baseline information about arbeitsspeicher.", "Summary and baseline information about memory."),
    ("Summary and baseline information about datenträger.", "Summary and baseline information about drives."),
    ("Security-related information and assessment for antivirus-schutz.", "Security-related information and assessment for antivirus protection."),
    ("Security-related information and assessment for defender-signaturen.", "Security-related information and assessment for defender signatures."),
    ("Security-related information and assessment for bitlocker & tpm.", "Security-related information and assessment for BitLocker & TPM."),
    ("Security-related information and assessment for zertifikate.", "Security-related information and assessment for certificates."),
    ("Security-related information and assessment for wichtige dienste.", "Security-related information and assessment for important services."),
    ("Security-related information and assessment for lokale administratoren / privilegierte gruppen.", "Security-related information and assessment for local administrators / privileged groups."),
    ("Network-related information and details for remote-zugriff.", "Network-related information and details for remote access."),
    ("Network-related information and details for externe internet-ip.", "Network-related information and details for external internet IP."),
    ("Network-related information and details for zeitdienst / ntp.", "Network-related information and details for time service / NTP."),
    ("Domain: Aktiviert / Private: Aktiviert / Public: Aktiviert", "Domain: Enabled / Private: Enabled / Public: Enabled"),
    ("Standalone Workstation – DC basic check auf diesem System nicht relevant", "Standalone Workstation – DC basic check not relevant on this system"),
    ("Information about updates, software and status of verfügbare windows-updates.", "Information about updates, software and status of available Windows updates."),
    ("Zuordnung von Prozessen zu den darin laufenden Windows-Diensten.", "Mapping of processes to the Windows services running inside them."),
    ("Zuletzt aufgelöste DNS-Einträge des lokalen Systems.", "Most recently resolved DNS entries of the local system."),
("Inventarliste aus der Anmeldeinformationsverwaltung mit Ziel und Benutzer, jedoch ohne Passwörter oder geheime Inhalte.", "Inventory from Windows Credential Manager showing targets and usernames only, without passwords or secret contents."),
    ("Gespeicherte WLAN-Profile mit SSID, Authentifizierung und Verschlüsselung, aber ohne Klartext-Schlüssel.", "Saved Wi-Fi profiles with SSID, authentication and encryption, but without plaintext keys."),
    ("windows vs. eigene", "Windows vs. custom"),
    ("auf diesem System nicht relevant", "not relevant on this system"),
    ("Aktiviert", "Enabled"),
    ("Lizenziert", "Licensed"),
    ("Hersteller", "Manufacturer"),
    ("Benutzer", "User"),
    ("Zeitzonen-ID", "Time Zone ID"),
    ("Antivirus aktiv", "Antivirus Enabled"),
    ("Echtzeitschutz", "Real-Time Protection"),
    ("Dienststatus", "Service Status"),
    ("Starttyp", "Start Type"),
    ("Produktname", "Product Name"),
    ("Bank Label", "Bank Label"),
    ("Kapazität (GB)", "Capacity (GB)"),
    ("Takt (MHz)", "Speed (MHz)"),
    ("Teilenummer", "Part Number"),
    ("Installierte Updates", "Installed Updates"),
    ("Gängige Ports", "Common Ports"),
    ("Netzmaske", "Subnet Mask"),
    ("Zeit", "Time"),
    ("Pfad", "Path"),
    ("Zielnetz", "Destination Prefix"),
    ("Gateway", "Gateway"),
    ("Metrik", "Metric"),
    ("InterfaceAlias", "Interface Alias"),
    ("Laufwerk", "Drive"),
    ("Prozess", "Process"),
    ("Prozess-ID", "Process ID"),
    ("Systeminfo", "System Information"),
    ("Externe IP", "External IP"),
    ("Netzwerk vertiefen", "Network Deep Dive"),
    ("Lokale Administratoren / privilegierte Gruppen", "Local Administrators / Privileged Groups"),
    ("Lokale Administratoren", "Local Administrators"),
    ("Verfügbare Windows-Updates", "Available Windows Updates"),
    ("Historie / Vergleich zum letzten Lauf", "History / Comparison with Previous Run"),
    ("Detailed system and inventory information for historie / vergleich zum letzten lauf.", "Detailed system and inventory information for history / comparison with previous run."),
    ("Detailed system and inventory information for eventlog-kurzcheck.", "Detailed system and inventory information for event log quick check."),
    ("Information about updates, software and status of verfügbare windows-updates.", "Information about updates, software and status of available Windows updates."),
    ("Information about updates, software and status of neustartstatus.", "Information about updates, software and status of reboot status."),
    ("Time source konnte nicht direkt abgefragt werden", "Time source could not be queried directly"),
    ("Microsoft Defender Antivirus schützt aktiv.", "Microsoft Defender Antivirus is actively protecting."),
    ("Kein vorheriger Report für Vergleich vorhanden", "No previous report available for comparison"),
    ("Vorheriger Report gefunden", "Previous report found"),
    ("Vorheriger Lauf", "Previous run"),
    ("Neue Warnungen/Kritisch", "New warnings / critical"),
    ("Behobene Warnungen/Kritisch", "Resolved warnings / critical"),
    ("Neue relevante Ports", "New relevant ports"),
    ("Neue Freigaben", "New shares"),
    ("Aktive Sitzung(en)", "Active session(s)"),
    ("Admins: ", "Admins: "),
    ("RDP-Benutzer", "RDP Users"),
    ("Primärer Schutz", "Primary protection"),
    ("Realtime", "Real-time"),
]

def localize_text(value: Any) -> str:
    text = str(value or "")
    if CURRENT_LANG != "en" or not text:
        return text

    exact_title = TITLE_LABELS_I18N["en"].get(text)
    if exact_title:
        return exact_title

    exact_category = CATEGORY_LABELS_I18N["en"].get(text)
    if exact_category:
        return exact_category

    exact_health = HEALTH_LABELS_I18N["en"].get(text)
    if exact_health:
        return exact_health

    lower_text = text.lower()
    for source, target in TITLE_LABELS_I18N.get("en", {}).items():
        if source.lower() == lower_text:
            return target
    for source, target in CATEGORY_LABELS_I18N.get("en", {}).items():
        if source.lower() == lower_text:
            return target

    for source, target in sorted(PHRASE_REPLACEMENTS_EN, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(source, target)

    return text

def translate_title(title: str) -> str:
    return TITLE_LABELS_I18N.get(CURRENT_LANG, {}).get(title, localize_text(title))

def translate_category(category: str) -> str:
    return CATEGORY_LABELS_I18N.get(CURRENT_LANG, {}).get(category, localize_text(category))

def translate_health_label(label: str) -> str:
    return HEALTH_LABELS_I18N.get(CURRENT_LANG, {}).get(label, localize_text(label))

def display_label(key: Any) -> str:
    text = str(key)
    if CURRENT_LANG == "en":
        if text in DISPLAY_LABELS_EN:
            return DISPLAY_LABELS_EN[text]
        base = DISPLAY_LABELS.get(text, text.replace("_", " "))
        return localize_text(base)
    return DISPLAY_LABELS.get(text, text.replace("_", " "))


def parse_date_safe(value: Any) -> dt.date | None:
    text = str(value or "").strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d.%m.%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    try:
        return dt.datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return default

    text = text.replace(',', '.')
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def collect_os_version() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $os = Get-WmiObject -Class Win32_OperatingSystem

        try {
            $feature = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -Name "DisplayVersion" -ErrorAction Stop).DisplayVersion
        } catch {
            try {
                $feature = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -Name "ReleaseId" -ErrorAction Stop).ReleaseId
            } catch {
                $feature = "unbekannt"
            }
        }

        [PSCustomObject]@{
            OS_Name        = $os.Caption
            OS_Version     = $os.Version
            Buildnummer    = $os.BuildNumber
            Architektur    = $os.OSArchitecture
            Feature_Update = $feature
        } | ConvertTo-Json -Compress
        """
    )

    summary = f'{data.get("OS_Name", "")} | Build {data.get("Buildnummer", "")} | {data.get("Feature_Update", "")}'
    return make_result(
        "os_version",
        "Betriebssystem",
        "Übersicht",
        20,
        "kv",
        data,
        summary=summary,
    )


def collect_uptime() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $os = Get-WmiObject -Class Win32_OperatingSystem
        $lastBoot = $os.LastBootUpTime
        $lastBootDt = [System.Management.ManagementDateTimeConverter]::ToDateTime($lastBoot)
        $uptime = (Get-Date) - $lastBootDt

        [PSCustomObject]@{
          Letzter_Boot = $lastBootDt.ToString("yyyy-MM-dd HH:mm:ss")
          Uptime       = ("{0}d {1}h {2}m" -f $uptime.Days, $uptime.Hours, $uptime.Minutes)
          Uptime_Tage  = $uptime.Days
        } | ConvertTo-Json -Compress
        """
    )

    status = "ok"
    issues = []
    if data.get("Uptime_Tage", 0) > 45:
        status = "warning"
        issues.append("System läuft seit mehr als 45 Tagen ohne Neustart.")

    return make_result(
        "uptime",
        "Uptime",
        "Übersicht",
        30,
        "kv",
        data,
        status=status,
        summary=data.get("Uptime", ""),
        issues=issues,
    )


def collect_cpu() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            Get-CimInstance -Class Win32_Processor |
            Select-Object Name, NumberOfCores, NumberOfLogicalProcessors |
            ConvertTo-Json -Compress
            """
        )
    )

    summary = ", ".join(item.get("Name", "") for item in data[:2])
    return make_result(
        "cpu",
        "CPU",
        "Übersicht",
        40,
        "table",
        data,
        summary=summary,
    )


def collect_memory() -> dict[str, Any]:
    data = powershell_json(
        r"""
        try {
          $os = Get-CimInstance -ClassName Win32_OperatingSystem
          $modules = @(Get-CimInstance -ClassName Win32_PhysicalMemory -ErrorAction SilentlyContinue)
          $arrays = @(Get-CimInstance -ClassName Win32_PhysicalMemoryArray -ErrorAction SilentlyContinue)

          $total = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
          $free = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
          $used = [math]::Round($total - $free, 2)
          $percent = if ($total -gt 0) { [math]::Round(($used / $total) * 100, 1) } else { 0 }

          $installedModules = $modules.Count
          $totalSlots = 0
          foreach ($array in $arrays) {
            if ($array.MemoryDevices) {
              $totalSlots += [int]$array.MemoryDevices
            }
          }

          $moduleList = @()
          foreach ($m in $modules) {
            $moduleList += [PSCustomObject]@{
              BankLabel    = $m.BankLabel
              Capacity_GB  = if ($m.Capacity) { [math]::Round($m.Capacity / 1GB, 2) } else { 0 }
              Speed_MHz    = $m.Speed
              Manufacturer = $m.Manufacturer
              PartNumber   = (($m.PartNumber | Out-String).Trim())
            }
          }

          [PSCustomObject]@{
            Gesamt_GB          = $total
            Frei_GB            = $free
            Belegt_GB          = $used
            Auslastung_Prozent = $percent
            RAM_Module_Belegt  = $installedModules
            RAM_Slots_Gesamt   = $totalSlots
            RAM_Slots_Frei     = if ($totalSlots -gt 0) { $totalSlots - $installedModules } else { $null }
            RAM_Module_Details = $moduleList
          } | ConvertTo-Json -Compress -Depth 5
        } catch {
          [PSCustomObject]@{
            Error = $_.Exception.Message
          } | ConvertTo-Json -Compress
        }
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Arbeitsspeicher-Modul lieferte kein Dictionary zurück.")

    if data.get("Error"):
        raise RuntimeError(data["Error"])

    usage = float(data.get("Auslastung_Prozent", 0))
    status = "ok"
    issues = []

    if usage >= 90:
        status = "critical"
        issues.append(f"RAM-Auslastung kritisch: {usage} %")
    elif usage >= 80:
        status = "warning"
        issues.append(f"RAM-Auslastung erhöht: {usage} %")

    summary = f"{usage} % belegt | Module: {data.get('RAM_Module_Belegt', 0)}"

    return make_result(
        "memory",
        "Arbeitsspeicher",
        "Übersicht",
        50,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_disk() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            Get-WmiObject -Class Win32_LogicalDisk |
            Where-Object { $_.DriveType -eq 3 } |
            Select-Object `
              @{Name="Laufwerk";Expression={$_.DeviceID}},
              @{Name="Gesamt_GB";Expression={ if ($null -ne $_.Size) { [math]::Round([double]$_.Size / 1GB, 2) } else { $null } }},
              @{Name="Frei_GB";Expression={ if ($null -ne $_.FreeSpace) { [math]::Round([double]$_.FreeSpace / 1GB, 2) } else { $null } }},
              @{Name="Belegt_GB";Expression={ if ($null -ne $_.Size -and $null -ne $_.FreeSpace) { [math]::Round(([double]$_.Size - [double]$_.FreeSpace) / 1GB, 2) } else { $null } }},
              @{Name="Auslastung_%";Expression={ if ($null -ne $_.Size -and [double]$_.Size -gt 0 -and $null -ne $_.FreeSpace) { [math]::Round((([double]$_.Size - [double]$_.FreeSpace) / [double]$_.Size) * 100, 1) } else { $null } }},
              @{Name="VolumeName";Expression={[string]$_.VolumeName}} |
            ConvertTo-Json -Compress
            """
        )
    )

    status = "ok"
    issues: list[str] = []

    for disk in data:
        usage = safe_float(disk.get("Auslastung_%", 0))
        drive = str(disk.get("Laufwerk", "?") or "?").strip()
        free_gb = disk.get("Frei_GB", "–")
        total_gb = disk.get("Gesamt_GB", "–")
        volume_name = str(disk.get("VolumeName", "") or "").strip()

        detail_parts = []
        if volume_name:
            detail_parts.append(f"Label: {volume_name}")
        detail_parts.append(f"Frei: {free_gb} GB von {total_gb} GB")

        row_status = "ok"
        if usage >= 90:
            row_status = "critical"
            status = "critical"
            note = f"Kritisch belegt ({usage} %)"
            issues.append(f"{drive} ist kritisch belegt ({usage} %).")
        elif usage >= 80:
            row_status = "warning"
            if status != "critical":
                status = "warning"
            note = f"Hoch belegt ({usage} %)"
            issues.append(f"{drive} ist hoch belegt ({usage} %).")
        else:
            note = f"Ausreichend frei ({usage} % belegt)"

        disk["Status"] = row_status
        disk["Details"] = " | ".join(detail_parts)
        disk["Hinweis"] = note
        disk["__row_status"] = row_status

    summary = f"{len(data)} Laufwerk(e) geprüft"
    return make_result(
        "disk",
        "Datenträger",
        "Übersicht",
        60,
        "table",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )

def collect_physical_disks() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Clean-String($value) {
          if ($null -eq $value) { return "" }
          return ([string]$value).Trim()
        }

        function Has-Prop($obj, [string]$name) {
          return ($null -ne $obj -and $obj.PSObject.Properties.Match($name).Count -gt 0)
        }

        function Normalize-MediaType([string]$value, [string]$model, [string]$busType) {
          $text = (Clean-String $value)
          $modelText = (Clean-String $model).ToLowerInvariant()
          $busText = (Clean-String $busType).ToLowerInvariant()

          if ($text) {
            if ($text -match 'SSD|NVMe|SCM') { return "SSD" }
            if ($text -match 'HDD|Hard Disk|Fixed hard disk') { return "HDD" }
          }

          if ($busText -match 'nvme') {
            return "SSD"
          }

          if ($modelText -match 'ssd|nvme|solid state') {
            return "SSD"
          }

          if ($modelText -match 'hdd|hard disk') {
            return "HDD"
          }

          return "Unbekannt"
        }

        $disks = @()
        $queryMode = ""
        $queryError = ""

        try {
          $physicalCmd = Get-Command Get-PhysicalDisk -ErrorAction SilentlyContinue
          $reliabilityAvailable = [bool](Get-Command Get-StorageReliabilityCounter -ErrorAction SilentlyContinue)

          if ($physicalCmd) {
            $queryMode = "Get-PhysicalDisk"

            $diskMap = @{}
            try {
              foreach ($disk in @(Get-Disk -ErrorAction SilentlyContinue)) {
                $diskMap["$($disk.Number)"] = $disk
              }
            } catch {}

            foreach ($pd in @(Get-PhysicalDisk -ErrorAction Stop)) {
              $deviceId = ""
              try { $deviceId = [string]$pd.DeviceId } catch {}

              $disk = $null
              if ($deviceId -and $diskMap.ContainsKey($deviceId)) {
                $disk = $diskMap[$deviceId]
              }

              $reliability = $null
              if ($reliabilityAvailable) {
                try {
                  $reliability = Get-StorageReliabilityCounter -PhysicalDisk $pd -ErrorAction Stop
                } catch {}
              }

              $model = Clean-String $pd.FriendlyName
              if (-not $model -and $disk -and (Has-Prop $disk "FriendlyName")) {
                $model = Clean-String $disk.FriendlyName
              }

              $serial = Clean-String $pd.SerialNumber
              if (-not $serial -and $disk -and (Has-Prop $disk "SerialNumber")) {
                $serial = Clean-String $disk.SerialNumber
              }

              $busType = ""
              if ($disk -and (Has-Prop $disk "BusType") -and $disk.BusType) {
                $busType = [string]$disk.BusType
              } elseif ((Has-Prop $pd "BusType") -and $pd.BusType) {
                $busType = [string]$pd.BusType
              }

              $mediaType = ""
              if ((Has-Prop $pd "MediaType") -and $pd.MediaType) {
                $mediaType = [string]$pd.MediaType
              }
              $mediaType = Normalize-MediaType $mediaType $model $busType

              $healthStatus = if ((Has-Prop $pd "HealthStatus") -and $pd.HealthStatus) {
                [string]$pd.HealthStatus
              } else {
                "Unbekannt"
              }

              $operationalStatus = "Unbekannt"
              if ((Has-Prop $pd "OperationalStatus") -and $pd.OperationalStatus) {
                if ($pd.OperationalStatus -is [array]) {
                  $operationalStatus = (($pd.OperationalStatus | ForEach-Object { [string]$_ }) -join ", ")
                } else {
                  $operationalStatus = [string]$pd.OperationalStatus
                }
              }

              $sizeGb = 0
              if ((Has-Prop $pd "Size") -and $pd.Size) {
                $sizeGb = [math]::Round([double]$pd.Size / 1GB, 2)
              } elseif ($disk -and (Has-Prop $disk "Size") -and $disk.Size) {
                $sizeGb = [math]::Round([double]$disk.Size / 1GB, 2)
              }

              $temperature = $null
              $predictFailure = $null
              $powerOnHours = $null

              if ($reliability) {
                if (Has-Prop $reliability "Temperature" -and $null -ne $reliability.Temperature) {
                  $temperature = [int]$reliability.Temperature
                }

                if (Has-Prop $reliability "PredictFailure" -and $null -ne $reliability.PredictFailure) {
                  $predictFailure = [bool]$reliability.PredictFailure
                }

                if (Has-Prop $reliability "PowerOnHours" -and $null -ne $reliability.PowerOnHours) {
                  $powerOnHours = [int64]$reliability.PowerOnHours
                }
              }

              $indexValue = ""
              if ($disk -and (Has-Prop $disk "Number") -and $null -ne $disk.Number) {
                $indexValue = [int]$disk.Number
              } elseif ($deviceId) {
                $indexValue = $deviceId
              }

              $disks += [PSCustomObject]@{
                Index             = $indexValue
                Model             = $model
                SerialNumber      = $serial
                MediaType         = $mediaType
                BusType           = $busType
                HealthStatus      = $healthStatus
                OperationalStatus = $operationalStatus
                Size_GB           = $sizeGb
                Temperature_C     = $temperature
                PredictFailure    = $predictFailure
                PowerOnHours      = $powerOnHours
              }
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        if (-not $disks -or @($disks).Count -eq 0) {
          try {
            $queryMode = if ($queryMode) { $queryMode + " / Win32_DiskDrive" } else { "Win32_DiskDrive" }

            foreach ($d in @(Get-CimInstance Win32_DiskDrive -ErrorAction Stop)) {
              $model = Clean-String $d.Model
              $serial = Clean-String $d.SerialNumber
              $busType = Clean-String $d.InterfaceType
              $mediaType = Normalize-MediaType (Clean-String $d.MediaType) $model $busType

              $disks += [PSCustomObject]@{
                Index             = if ($null -ne $d.Index) { [int]$d.Index } else { "" }
                Model             = $model
                SerialNumber      = $serial
                MediaType         = $mediaType
                BusType           = $busType
                HealthStatus      = "Unbekannt"
                OperationalStatus = "Unbekannt"
                Size_GB           = if ($d.Size) { [math]::Round([double]$d.Size / 1GB, 2) } else { 0 }
                Temperature_C     = $null
                PredictFailure    = $null
                PowerOnHours      = $null
              }
            }
          } catch {
            if (-not $queryError) {
              $queryError = $_.Exception.Message
            }
          }
        }

        $ssdCount = @($disks | Where-Object { $_.MediaType -eq "SSD" }).Count
        $hddCount = @($disks | Where-Object { $_.MediaType -eq "HDD" }).Count
        $unknownMediaCount = @($disks | Where-Object { $_.MediaType -eq "Unbekannt" }).Count

        [PSCustomObject]@{
          QueryMode          = $queryMode
          QueryError         = $queryError
          Disk_Count         = @($disks).Count
          SSD_Count          = $ssdCount
          HDD_Count          = $hddCount
          Unknown_Media_Count = $unknownMediaCount
          Disks              = $disks
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Physische-Datenträger-Modul lieferte kein Dictionary zurück.")

    disks = ensure_list(data.get("Disks", []))
    disk_count = int(data.get("Disk_Count", len(disks)) or 0)
    ssd_count = int(data.get("SSD_Count", 0) or 0)
    hdd_count = int(data.get("HDD_Count", 0) or 0)
    unknown_media_count = int(data.get("Unknown_Media_Count", 0) or 0)
    query_mode = str(data.get("QueryMode", "") or "").strip()
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if disk_count == 0:
        status = "warning"
        summary = "Physische Datenträger konnten nicht ermittelt werden"
        if query_error:
            issues.append(f"Datenträgerabfrage fehlgeschlagen: {query_error}")
        else:
            issues.append("Es wurden keine physischen Datenträgerdaten zurückgegeben.")
        return make_result(
            "physical_disks",
            "Physische Datenträger / SMART / Medientyp",
            "Inventar & Tiefeninfos",
            62,
            "sections",
            data,
            status=status,
            summary=summary,
            issues=issues,
        )

    all_health_unknown = True

    DISK_TEMP_INFO_C = 50
    DISK_TEMP_WARNING_C = 60
    DISK_TEMP_CRITICAL_C = 70

    for disk in disks:
        model = str(disk.get("Model", "") or "Datenträger").strip()
        health = str(disk.get("HealthStatus", "") or "").strip().lower()
        operational = str(disk.get("OperationalStatus", "") or "").strip().lower()
        media_type = str(disk.get("MediaType", "") or "").strip()
        temperature = disk.get("Temperature_C")
        predict_failure = disk.get("PredictFailure")

        if health and health not in {"unbekannt", "unknown"}:
            all_health_unknown = False

        if predict_failure is True:
            status = "critical"
            issues.append(f"{model}: SMART meldet möglichen Ausfall.")
            continue

        if "unhealthy" in health or "kritisch" in health or "fehler" in health:
            status = "critical"
            issues.append(f"{model}: Gesundheitsstatus kritisch ({disk.get('HealthStatus', '')}).")
            continue

        if isinstance(temperature, (int, float)) and temperature >= DISK_TEMP_CRITICAL_C:
            status = "critical"
            issues.append(f"{model}: Datenträgertemperatur kritisch ({temperature} °C).")
            continue

        if (
            "warning" in health
            or "degraded" in operational
            or "offline" in operational
            or "failed" in operational
            or "lost communication" in operational
        ):
            if status != "critical":
                status = "warning"
            issues.append(
                f"{model}: Auffälliger Status ({disk.get('HealthStatus', '')} / {disk.get('OperationalStatus', '')})."
            )
            continue

        if isinstance(temperature, (int, float)) and temperature >= DISK_TEMP_WARNING_C:
            if status != "critical":
                status = "warning"
            issues.append(f"{model}: Erhöhte Datenträgertemperatur ({temperature} °C).")
        elif isinstance(temperature, (int, float)) and temperature >= DISK_TEMP_INFO_C:
            if status == "ok":
                status = "info"
            issues.append(f"{model}: Datenträgertemperatur leicht erhöht ({temperature} °C).")

        if media_type == "Unbekannt" and status == "ok":
            status = "info"

    if all_health_unknown and status == "ok":
        status = "info"
        issues.append("Gesundheitsstatus/SMART-Daten sind auf diesem System nicht vollständig verfügbar.")

    if query_mode and query_mode != "Get-PhysicalDisk" and status == "ok":
        status = "info"
        issues.append("Erweiterte Datenträgerdaten wurden über WMI-Fallback ermittelt.")

    if query_error and status in {"ok", "info"}:
        status = "info"
        issues.append(f"Erweiterte Storage-Abfrage nur teilweise verfügbar: {query_error}")

    summary = f"{disk_count} physische Datenträger | SSD: {ssd_count} | HDD: {hdd_count}"
    if unknown_media_count > 0:
        summary += f" | Unklar: {unknown_media_count}"

    return make_result(
        "physical_disks",
        "Physische Datenträger / SMART / Medientyp",
        "Inventar & Tiefeninfos",
        62,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_hardware_identity_ids() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Has-Cmd($name) {
          return [bool](Get-Command $name -ErrorAction SilentlyContinue)
        }

        function Clean-String($value) {
          if ($null -eq $value) { return "" }
          return ([string]$value).Trim()
        }

        function Convert-WmiDateSafe($value) {
          try {
            if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
              return ""
            }
            return [System.Management.ManagementDateTimeConverter]::ToDateTime([string]$value).ToString("yyyy-MM-dd HH:mm:ss")
          } catch {
            return Clean-String $value
          }
        }

        function Decode-EdidField($bytes) {
          if ($null -eq $bytes) { return "" }
          $chars = New-Object System.Collections.Generic.List[char]
          foreach ($b in $bytes) {
            if ([int]$b -gt 0) {
              [void]$chars.Add([char][int]$b)
            }
          }
          return (-join $chars.ToArray()).Trim()
        }

        $collectionErrors = New-Object System.Collections.Generic.List[string]

        function Try-Collect([string]$label, [scriptblock]$scriptBlock, $fallback) {
          try {
            return & $scriptBlock
          } catch {
            [void]$script:collectionErrors.Add(("{0}: {1}" -f $label, $_.Exception.Message))
            return $fallback
          }
        }

        $hardwareUuid = Try-Collect "Hardware UUID" {
          Clean-String ((Get-CimInstance Win32_ComputerSystemProduct -ErrorAction Stop | Select-Object -First 1).UUID)
        } ""

        $biosObj = Try-Collect "BIOS" {
          Get-CimInstance Win32_BIOS -ErrorAction Stop | Select-Object -First 1
        } $null

        $biosId = if ($biosObj) {
          [PSCustomObject]@{
            SerialNumber       = Clean-String $biosObj.SerialNumber
            SMBIOSBIOSVersion  = Clean-String $biosObj.SMBIOSBIOSVersion
            Manufacturer       = Clean-String $biosObj.Manufacturer
          }
        } else {
          [PSCustomObject]@{}
        }

        $firmwareIds = if ($biosObj) {
          [PSCustomObject]@{
            Manufacturer       = Clean-String $biosObj.Manufacturer
            SerialNumber       = Clean-String $biosObj.SerialNumber
            SMBIOSBIOSVersion  = Clean-String $biosObj.SMBIOSBIOSVersion
            ReleaseDate        = Convert-WmiDateSafe $biosObj.ReleaseDate
          }
        } else {
          [PSCustomObject]@{}
        }

        $cpuIds = Try-Collect "CPU" {
          @(
            Get-CimInstance Win32_Processor -ErrorAction Stop |
            Select-Object ProcessorId, Name, Manufacturer, NumberOfCores, NumberOfLogicalProcessors
          )
        } @()

        $mainboardId = Try-Collect "Mainboard" {
          $bb = Get-CimInstance Win32_BaseBoard -ErrorAction Stop | Select-Object -First 1
          [PSCustomObject]@{
            SerialNumber = Clean-String $bb.SerialNumber
            Product      = Clean-String $bb.Product
            Manufacturer = Clean-String $bb.Manufacturer
            Version      = Clean-String $bb.Version
          }
        } ([PSCustomObject]@{})

        $networkIds = Try-Collect "Netzwerk" {
          if (Has-Cmd "Get-NetAdapter") {
            @(
              Get-NetAdapter -ErrorAction Stop |
              Select-Object Name, InterfaceDescription, MacAddress, InterfaceGuid, InterfaceIndex, Status, LinkSpeed
            )
          } else {
            @(
              Get-CimInstance Win32_NetworkAdapter -ErrorAction Stop |
              Where-Object { $_.MACAddress } |
              Select-Object `
                Name,
                @{Name="InterfaceDescription";Expression={$_.Description}},
                @{Name="MacAddress";Expression={$_.MACAddress}},
                @{Name="InterfaceGuid";Expression={$_.GUID}},
                @{Name="InterfaceIndex";Expression={$_.InterfaceIndex}},
                NetConnectionStatus
            )
          }
        } @()

        $machineGuid = Try-Collect "MachineGuid" {
          Clean-String ((Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Cryptography" -Name MachineGuid -ErrorAction Stop).MachineGuid)
        } ""

        $windowsProductId = Try-Collect "Windows ProductId" {
          Clean-String ((Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -Name ProductId -ErrorAction Stop).ProductId)
        } ""

        $windowsIds = [PSCustomObject]@{
          MachineGuid      = $machineGuid
          WindowsProductId = $windowsProductId
        }

        $storageWwn = Try-Collect "Storage WWN" {
          if (Has-Cmd "Get-PhysicalDisk") {
            @(
              Get-PhysicalDisk -ErrorAction Stop |
              Select-Object FriendlyName, SerialNumber, UniqueId, BusType, MediaType, HealthStatus
            )
          } else {
            @()
          }
        } @()

        $storageIds = Try-Collect "Storage IDs" {
          @(
            Get-CimInstance Win32_DiskDrive -ErrorAction Stop |
            Select-Object `
              Index,
              Model,
              SerialNumber,
              InterfaceType,
              PNPDeviceID,
              DeviceID,
              @{Name="Size_GB";Expression={ if ($_.Size) { [math]::Round([double]$_.Size / 1GB, 2) } else { $null } }}
          )
        } @()

        $nvmeIds = @(
          $storageWwn |
          Where-Object { [string]$_.BusType -eq "NVMe" } |
          Select-Object FriendlyName, SerialNumber, UniqueId, BusType, HealthStatus
        )

        $gpuIds = Try-Collect "GPU" {
          @(
            Get-CimInstance Win32_VideoController -ErrorAction Stop |
            Select-Object Name, PNPDeviceID, AdapterCompatibility, DriverVersion
          )
        } @()

        $tpmInfo = Try-Collect "TPM" {
          $tpm = Get-CimInstance -Namespace root\cimv2\security\microsofttpm Win32_Tpm -ErrorAction Stop | Select-Object -First 1
          if ($tpm) {
            [PSCustomObject]@{
              ManufacturerId          = $tpm.ManufacturerId
              ManufacturerIdTxt       = Clean-String $tpm.ManufacturerIdTxt
              ManufacturerVersion     = Clean-String $tpm.ManufacturerVersion
              SpecVersion             = Clean-String $tpm.SpecVersion
              IsEnabled_InitialValue  = $tpm.IsEnabled_InitialValue
              IsActivated_InitialValue = $tpm.IsActivated_InitialValue
              IsOwned_InitialValue    = $tpm.IsOwned_InitialValue
            }
          } else {
            [PSCustomObject]@{}
          }
        } ([PSCustomObject]@{})

        $ramSerials = Try-Collect "RAM" {
          @(
            Get-CimInstance Win32_PhysicalMemory -ErrorAction Stop |
            Select-Object `
              Manufacturer,
              SerialNumber,
              PartNumber,
              DeviceLocator,
              @{Name="Capacity_GB";Expression={ if ($_.Capacity) { [math]::Round([double]$_.Capacity / 1GB, 2) } else { $null } }}
          )
        } @()

        $monitorIds = Try-Collect "Monitore" {
          @(
            Get-CimInstance WmiMonitorID -Namespace root\wmi -ErrorAction Stop |
            ForEach-Object {
              [PSCustomObject]@{
                ManufacturerName = Decode-EdidField $_.ManufacturerName
                UserFriendlyName = Decode-EdidField $_.UserFriendlyName
                SerialNumber     = Decode-EdidField $_.SerialNumberID
                InstanceName     = Clean-String $_.InstanceName
              }
            }
          )
        } @()

        $usbIds = Try-Collect "USB" {
          if (Has-Cmd "Get-PnpDevice") {
            @(
              Get-PnpDevice -PresentOnly -ErrorAction Stop |
              Where-Object { $_.InstanceId -match '^USB' } |
              Select-Object FriendlyName, Class, InstanceId, Status
            )
          } else {
            @()
          }
        } @()

        $pciIds = Try-Collect "PCI" {
          if (Has-Cmd "Get-PnpDevice") {
            @(
              Get-PnpDevice -ErrorAction Stop |
              Where-Object { $_.InstanceId -match '^PCI' } |
              Select-Object FriendlyName, Class, InstanceId, Status
            )
          } else {
            @()
          }
        } @()

        $soundIds = Try-Collect "Sound" {
          @(
            Get-CimInstance Win32_SoundDevice -ErrorAction Stop |
            Select-Object Name, Manufacturer, PNPDeviceID, Status
          )
        } @()

        $bluetoothIds = Try-Collect "Bluetooth" {
          if (Has-Cmd "Get-PnpDevice") {
            @(
              Get-PnpDevice -Class Bluetooth -ErrorAction Stop |
              Select-Object FriendlyName, InstanceId, Status
            )
          } else {
            @()
          }
        } @()

        $batteryInfo = Try-Collect "Akku" {
          @(
            Get-CimInstance Win32_Battery -ErrorAction Stop |
            Select-Object DeviceID, Name, Status, Chemistry
          )
        } @()

        $chassisInfo = Try-Collect "Chassis" {
          $ch = Get-CimInstance Win32_SystemEnclosure -ErrorAction Stop | Select-Object -First 1
          [PSCustomObject]@{
            SerialNumber = Clean-String $ch.SerialNumber
            Manufacturer = Clean-String $ch.Manufacturer
            SMBIOSAssetTag = Clean-String $ch.SMBIOSAssetTag
            ChassisTypes = if ($ch.ChassisTypes) { @($ch.ChassisTypes) -join ", " } else { "" }
          }
        } ([PSCustomObject]@{})

        [PSCustomObject]@{
          Hardware_UUID          = $hardwareUuid
          Bios_ID                = $biosId
          Firmware_IDs           = $firmwareIds
          CPU_IDs                = $cpuIds
          Mainboard_ID           = $mainboardId
          Network_IDs            = $networkIds
          Windows_IDs            = $windowsIds
          Storage_WWN            = $storageWwn
          Storage_IDs            = $storageIds
          GPU_IDs                = $gpuIds
          RAM_Serials            = $ramSerials
          Monitor_IDs            = $monitorIds
          USB_Device_IDs         = $usbIds
          PCI_Device_IDs         = $pciIds
          Sound_Device_IDs       = $soundIds
          Bluetooth_Device_IDs   = $bluetoothIds
          Battery_Info           = $batteryInfo
          Chassis_Info           = $chassisInfo
          NVMe_Storage_IDs       = $nvmeIds
          CollectionErrors       = $collectionErrors
        } | ConvertTo-Json -Compress -Depth 8
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Hardware-ID-Modul lieferte kein Dictionary zurück.")

    windows_ids = data.get("Windows_IDs", {}) if isinstance(data.get("Windows_IDs", {}), dict) else {}
    major_available = 0

    if str(data.get("Hardware_UUID", "") or "").strip():
        major_available += 1
    if str(windows_ids.get("MachineGuid", "") or "").strip():
        major_available += 1
    if len(ensure_list(data.get("CPU_IDs", []))) > 0:
        major_available += 1
    if len(ensure_list(data.get("Storage_IDs", []))) > 0:
        major_available += 1
    if len(ensure_list(data.get("Network_IDs", []))) > 0:
        major_available += 1

    usb_count = len(ensure_list(data.get("USB_Device_IDs", [])))
    pci_count = len(ensure_list(data.get("PCI_Device_IDs", [])))
    monitor_count = len(ensure_list(data.get("Monitor_IDs", [])))

    raw_errors = [str(x).strip() for x in ensure_list(data.get("CollectionErrors", [])) if str(x).strip()]
    suppressed_error_prefixes = (
        "TPM: Zugriff verweigert",
    )
    errors = [
        err for err in raw_errors
        if not any(err.startswith(prefix) for prefix in suppressed_error_prefixes)
    ]

    if errors:
        data["CollectionErrors"] = errors
    else:
        data.pop("CollectionErrors", None)

    status = "ok"
    issues: list[str] = []

    if major_available <= 2:
        status = "warning"
        issues.append("Mehrere Kern-IDs konnten nicht ermittelt werden.")
    elif major_available < 5:
        status = "info"
        issues.append("Ein Teil der Kern-IDs ist vorhanden, aber nicht alles konnte gelesen werden.")

    if errors:
        if status == "ok":
            status = "info"
        issues.append(f"Teilfehler bei einzelnen ID-Abfragen: {len(errors)}")

    summary = (
        f"Kernbereiche: {major_available}/5 | "
        f"USB: {usb_count} | PCI: {pci_count} | Monitore: {monitor_count}"
    )

    return make_result(
        "hardware_identity_ids",
        "Hardware- / Geräte-IDs",
        "Inventar & Tiefeninfos",
        63,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_network() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            $adapters = Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled }

            $list = foreach ($a in $adapters) {
              $ips = if ($a.IPAddress) { $a.IPAddress -join ", " } else { "" }
              $subnets = if ($a.IPSubnet) { $a.IPSubnet -join ", " } else { "" }
              $gw = if ($a.DefaultIPGateway) { $a.DefaultIPGateway -join ", " } else { "" }
              $dns = if ($a.DNSServerSearchOrder) { $a.DNSServerSearchOrder -join ", " } else { "" }

              [PSCustomObject]@{
                Beschreibung = $a.Description
                MACAdresse = $a.MACAddress
                IPs = $ips
                Netzmaske = $subnets
                Gateway = $gw
                DNS_Server = $dns
              }
            }

            $list | ConvertTo-Json -Compress
            """
        )
    )

    return make_result(
        "network",
        "Netzwerkadapter",
        "Netzwerk",
        70,
        "table",
        data,
        summary=f"{len(data)} Adapter aktiv",
    )


def collect_firewall() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            Get-NetFirewallProfile |
            Select-Object Name, @{Name="Status";Expression={if ($_.Enabled) { "Aktiviert" } else { "Deaktiviert" }}} |
            ConvertTo-Json -Compress
            """
        )
    )

    disabled = [item["Name"] for item in data if item.get("Status") == "Deaktiviert"]
    status = "ok"
    issues = []

    if disabled:
        status = "critical"
        issues.append(f"Firewall deaktiviert in: {', '.join(disabled)}")

    return make_result(
        "firewall",
        "Firewall",
        "Sicherheit",
        80,
        "table",
        data,
        status=status,
        summary=" / ".join(f"{x.get('Name')}: {x.get('Status')}" for x in data),
        issues=issues,
    )


def collect_defender() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $svc = Get-Service -Name WinDefend -ErrorAction SilentlyContinue
        $mpCmd = Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue

        $defender = $null
        if ($mpCmd) {
          $mp = Get-MpComputerStatus
          $defender = [PSCustomObject]@{
            AMServiceEnabled          = $mp.AMServiceEnabled
            AMRunningMode             = $mp.AMRunningMode
            AntivirusEnabled          = $mp.AntivirusEnabled
            RealTimeProtectionEnabled = $mp.RealTimeProtectionEnabled
            SignatureUpdated          = $mp.SignatureUpdated
            ProductStatus             = $mp.ProductStatus
            AntispywareEnabled        = $mp.AntispywareEnabled
            AntimalwareEnabled        = $mp.AntimalwareEnabled
            NISEnabled                = $mp.NISEnabled
            IoavProtectionEnabled     = $mp.IoavProtectionEnabled
            BehaviorMonitorEnabled    = $mp.BehaviorMonitorEnabled
            ServiceStatus             = if ($svc) { $svc.Status.ToString() } else { "Nicht gefunden" }
            ServiceStartType          = if ($svc) { $svc.StartType.ToString() } else { "n/a" }
          }
        } else {
          $defender = [PSCustomObject]@{
            AMServiceEnabled          = $null
            AMRunningMode             = $null
            AntivirusEnabled          = $null
            RealTimeProtectionEnabled = $null
            SignatureUpdated          = $null
            ProductStatus             = $null
            ServiceStatus             = if ($svc) { $svc.Status.ToString() } else { "Nicht gefunden" }
            ServiceStartType          = if ($svc) { $svc.StartType.ToString() } else { "n/a" }
            Note                      = "Get-MpComputerStatus nicht verfügbar"
          }
        }

        $avProducts = @()
        try {
          $rawProducts = Get-CimInstance -Namespace root\SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop |
            Select-Object displayName, pathToSignedProductExe, productState

          $seen = @{}
          foreach ($p in $rawProducts) {
            $key = "$($p.displayName)|$($p.pathToSignedProductExe)"
            if (-not $seen.ContainsKey($key)) {
              $seen[$key] = $true
              $avProducts += [PSCustomObject]@{
                DisplayName = $p.displayName
                Path        = $p.pathToSignedProductExe
                ProductState = $p.productState
              }
            }
          }
        } catch {
          $avProducts = @()
        }

        [PSCustomObject]@{
          Defender = $defender
          AntivirusProducts = $avProducts
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    defender = data.get("Defender", {}) if isinstance(data, dict) else {}
    av_products = ensure_list(data.get("AntivirusProducts", [])) if isinstance(data, dict) else []

    third_party = []
    defender_products = []

    for item in av_products:
        name = str(item.get("DisplayName", "")).strip()
        if not name:
            continue
        if "defender" in name.lower():
            defender_products.append(item)
        else:
            third_party.append(item)

    third_party_names = sorted({str(x.get("DisplayName", "")).strip() for x in third_party if x.get("DisplayName")})

    service_status = str(defender.get("ServiceStatus", ""))
    av_enabled = defender.get("AntivirusEnabled")
    rtp_enabled = defender.get("RealTimeProtectionEnabled")

    status = "ok"
    issues = []

    if third_party_names:
        status = "ok"
        issues.append(f"Drittanbieter-Antivirus erkannt: {', '.join(third_party_names)}")
    elif service_status == "Running" and av_enabled is True and rtp_enabled is True:
        status = "ok"
        issues.append("Microsoft Defender Antivirus schützt aktiv.")
    elif defender.get("AMServiceEnabled") is None:
        status = "info"
        issues.append("Defender-Cmdlets nicht verfügbar; AV-Erkennung nur eingeschränkt möglich.")
    else:
        status = "warning"
        issues.append("Kein aktiver Antivirus-Schutz eindeutig erkennbar.")

    primary_protection = ", ".join(third_party_names) if third_party_names else "Microsoft Defender Antivirus"

    summary = (
        f"Primärer Schutz: {primary_protection} | "
        f"Defender-Dienst: {service_status} | "
        f"Defender AV: {av_enabled} | Realtime: {rtp_enabled}"
    )

    normalized = {
        "Primärer_Schutz": primary_protection,
        "Drittanbieter_Produkte": third_party,
        "Defender_Status": defender,
    }

    return make_result(
        "defender",
        "Antivirus-Schutz",
        "Sicherheit",
        90,
        "sections",
        normalized,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_bitlocker_tpm() -> dict[str, Any]:
    bitlocker = ensure_list(
        powershell_json(
            r"""
            if (Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue) {
              $volumes = Get-BitLockerVolume
              $result = @()
              foreach ($vol in $volumes) {
                $mount = $vol.MountPoint
                $driveLetter = $mount.Replace(":", "")
                $volumeInfo = Get-Volume -DriveLetter $driveLetter -ErrorAction SilentlyContinue

                $sizeGB = if ($null -ne $volumeInfo -and $volumeInfo.Size) {
                  [math]::Round($volumeInfo.Size / 1GB, 2)
                } else {
                  0
                }

                $entry = [ordered]@{
                  MountPoint = $mount
                  VolumeStatus = $vol.VolumeStatus.ToString()
                  ProtectionStatus = $vol.ProtectionStatus.ToString()
                  EncryptionMethod = if ($vol.EncryptionMethod) { $vol.EncryptionMethod.ToString() } else { "NotEncrypted" }
                  KeyProtectorTypes = if ($vol.KeyProtector.Count -gt 0) { ($vol.KeyProtector | ForEach-Object { $_.KeyProtectorType.ToString() }) -join ", " } else { "None" }
                  VolumeSizeGB = $sizeGB
                }

                $result += [PSCustomObject]$entry
              }
              $result | ConvertTo-Json -Compress
            } else {
              @([PSCustomObject]@{
                MountPoint = "-"
                VolumeStatus = "Unbekannt"
                ProtectionStatus = "Nicht verfügbar"
                EncryptionMethod = "Nicht verfügbar"
                KeyProtectorTypes = "Nicht verfügbar"
                VolumeSizeGB = 0
              }) | ConvertTo-Json -Compress
            }
            """
        )
    )

    tpm = powershell_json(
        r"""
        $specVersion = try {
          Get-WmiObject -Namespace "Root\CIMv2\Security\MicrosoftTpm" -Class Win32_Tpm |
            Select-Object -ExpandProperty SpecVersion
        } catch {
          "unavailable"
        }

        if (Get-Command Get-Tpm -ErrorAction SilentlyContinue) {
          $tpm = Get-Tpm
          $cleanVersion = if ($tpm.ManufacturerVersion) { $tpm.ManufacturerVersion.TrimEnd([char]0) } else { "" }

          [PSCustomObject]@{
            TpmPresent = $tpm.TpmPresent
            TpmReady = $tpm.TpmReady
            TpmEnabled = $tpm.TpmEnabled
            TpmActivated = $tpm.TpmActivated
            ManufacturerID = $tpm.ManufacturerID
            ManufacturerVersion = $cleanVersion
            SpecVersion = $specVersion
          } | ConvertTo-Json -Compress
        } else {
          [PSCustomObject]@{
            TpmPresent = $false
            TpmReady = $false
            TpmEnabled = $false
            TpmActivated = $false
            ManufacturerID = ""
            ManufacturerVersion = ""
            SpecVersion = "unavailable"
            Error = "Get-Tpm not supported on this system."
          } | ConvertTo-Json -Compress
        }
        """
    )

    status = "ok"
    issues = []

    for volume in bitlocker:
        protection = str(volume.get("ProtectionStatus", "")).lower()
        mount = volume.get("MountPoint", "?")
        if "on" not in protection and "aktiv" not in protection:
            status = "critical"
            issues.append(f"BitLocker-Schutz nicht aktiv auf {mount}.")

    if tpm.get("TpmPresent") is False and status != "critical":
        status = "warning"
        issues.append("TPM nicht vorhanden oder nicht verfügbar.")

    data = {
        "BitLocker": bitlocker,
        "TPM": tpm,
    }

    return make_result(
        "bitlocker_tpm",
        "BitLocker & TPM",
        "Sicherheit",
        100,
        "sections",
        data,
        status=status,
        summary="BitLocker- und TPM-Status geprüft",
        issues=issues,
    )


def collect_ports() -> dict[str, Any]:
    raw = powershell_json(
        r"""
        $commonPorts = @{
          20   = "FTP-Data"
          21   = "FTP"
          22   = "SSH"
          23   = "Telnet"
          25   = "SMTP"
          53   = "DNS"
          67   = "DHCP-Server"
          68   = "DHCP-Client"
          69   = "TFTP"
          80   = "HTTP"
          88   = "Kerberos"
          110  = "POP3"
          123  = "NTP"
          135  = "RPC Endpoint Mapper"
          137  = "NetBIOS Name"
          138  = "NetBIOS Datagram"
          139  = "NetBIOS Session"
          143  = "IMAP"
          161  = "SNMP"
          162  = "SNMP Trap"
          389  = "LDAP"
          443  = "HTTPS"
          445  = "SMB"
          465  = "SMTPS"
          514  = "Syslog"
          587  = "SMTP Submission"
          636  = "LDAPS"
          993  = "IMAPS"
          995  = "POP3S"
          1433 = "MS SQL"
          1434 = "MS SQL Browser"
          1521 = "Oracle"
          3306 = "MySQL"
          3389 = "RDP"
          5432 = "PostgreSQL"
          5900 = "VNC"
          5985 = "WinRM HTTP"
          5986 = "WinRM HTTPS"
          6379 = "Redis"
          8080 = "HTTP Alt"
          8443 = "HTTPS Alt"
          9100 = "Drucker / JetDirect"
        }

        $allListeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue)

        $filtered = foreach ($conn in $allListeners) {
          if ($commonPorts.ContainsKey([int]$conn.LocalPort)) {
            $procName = ""
            try {
              $proc = Get-Process -Id $conn.OwningProcess -ErrorAction Stop
              $procName = $proc.ProcessName
            } catch {
              $procName = ""
            }

            [PSCustomObject]@{
              LocalAddress      = $conn.LocalAddress
              LocalPort         = $conn.LocalPort
              Port_Beschreibung = $commonPorts[[int]$conn.LocalPort]
              OwningProcess     = $conn.OwningProcess
              ProcessName       = $procName
            }
          }
        }

        [PSCustomObject]@{
          VisiblePorts   = @($filtered | Sort-Object LocalPort, LocalAddress -Unique)
          TotalListening = $allListeners.Count
          VisibleCount   = @($filtered | Sort-Object LocalPort, LocalAddress -Unique).Count
        } | ConvertTo-Json -Compress -Depth 4
        """
    )

    if isinstance(raw, dict):
        visible_ports = ensure_list(raw.get("VisiblePorts", []))
        total_listening = int(raw.get("TotalListening", 0))
        visible_count = int(raw.get("VisibleCount", len(visible_ports)))
    else:
        visible_ports = ensure_list(raw)
        total_listening = len(visible_ports)
        visible_count = len(visible_ports)

    hidden_count = max(total_listening - visible_count, 0)

    issues = []
    status = "ok"

    sensitive_ports = {21, 23, 135, 137, 138, 139, 445}
    found_sensitive = [
        f"{item.get('LocalPort')} ({item.get('Port_Beschreibung', '')})"
        for item in visible_ports
        if int(item.get("LocalPort", 0)) in sensitive_ports
    ]

    if found_sensitive:
        status = "info"
        issues.append(f"Auffällige/gängige Infrastruktur-Ports aktiv: {', '.join(found_sensitive)}")

    summary = f"{visible_count} gängige Listening-Port(s) sichtbar"
    if hidden_count > 0:
        summary += f" | {hidden_count} sonstige ausgeblendet"

    return make_result(
        "ports",
        "Offene Ports",
        "Sicherheit",
        110,
        "sections",
        {
            "VisiblePorts": visible_ports,
            "TotalListening": total_listening,
            "VisibleCount": visible_count,
            "Ausgeblendet": hidden_count,
        },
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_certificates() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            $heute = Get-Date
            $warnung = $heute.AddDays(30)

            $list = Get-ChildItem -Path Cert:\LocalMachine\My -ErrorAction SilentlyContinue | Where-Object {
                $_.NotAfter -lt $warnung
            } | ForEach-Object {
                $daysRemaining = [int][Math]::Floor(($_.NotAfter - $heute).TotalDays)
                $status = if ($_.NotAfter -lt $heute) { "abgelaufen" } else { "bald ablaufend" }
                $rowSeverity = if ($daysRemaining -lt 0) { "critical" } else { "warning" }

                [PSCustomObject]@{
                    subject = $_.Subject
                    valid_until = $_.NotAfter.ToString("yyyy-MM-dd HH:mm:ss")
                    days_remaining = $daysRemaining
                    status = $status
                    __row_status = $rowSeverity
                }
            }

            $list | ConvertTo-Json -Compress
            """
        )
    )

    issues = []
    status = "ok"

    for cert in data:
        cert_status = str(cert.get("status", "")).lower()
        subject = cert.get("subject", "Zertifikat")
        if "abgelaufen" in cert_status:
            status = "critical"
            issues.append(report_tr("certificate_issue_expired", subject=subject))
        elif "bald" in cert_status and status != "critical":
            status = "warning"
            issues.append(report_tr("certificate_issue_expiring", subject=subject))

    summary = localize_text("Keine relevanten Zertifikate gefunden")
    if data:
        summary = report_tr("certificates_summary_findings", count=len(data))

    return make_result(
        "certificates",
        "Zertifikate",
        "Sicherheit",
        120,
        "table",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_pending_reboot() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Test-RegKeyExists($path) {
          try {
            return Test-Path $path
          } catch {
            return $false
          }
        }

        function Get-RegValueSafe($path, $name) {
          try {
            return (Get-ItemProperty -Path $path -Name $name -ErrorAction Stop).$name
          } catch {
            return $null
          }
        }

        $reasons = @()
        $details = [ordered]@{}

        $cbsPending = Test-RegKeyExists "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"
        $details["CBS_RebootPending"] = $cbsPending
        if ($cbsPending) {
          $reasons += "Component Based Servicing meldet einen ausstehenden Neustart."
        }

        $wuPending = Test-RegKeyExists "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
        $details["WindowsUpdate_RebootRequired"] = $wuPending
        if ($wuPending) {
          $reasons += "Windows Update verlangt einen Neustart."
        }

        $updateExeVolatile = Get-RegValueSafe "HKLM:\SOFTWARE\Microsoft\Updates" "UpdateExeVolatile"
        if ($null -eq $updateExeVolatile) {
          $updateExeVolatile = 0
        }
        $details["UpdateExeVolatile"] = [int]$updateExeVolatile
        if ([int]$updateExeVolatile -ne 0) {
          $reasons += "UpdateExeVolatile ist gesetzt."
        }

        $pendingRename = Get-RegValueSafe "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" "PendingFileRenameOperations"
        $pendingRenameCount = 0
        $pendingRenameSample = @()

        if ($pendingRename) {
          if ($pendingRename -is [array]) {
            $pendingRenameCount = $pendingRename.Count
            $pendingRenameSample = @($pendingRename | Select-Object -First 6)
          } else {
            $pendingRenameCount = 1
            $pendingRenameSample = @([string]$pendingRename)
          }

          if ($pendingRenameCount -gt 0) {
            $reasons += "Datei-/Treiber-Operationen warten auf Neustart (PendingFileRenameOperations)."
          }
        }

        $details["PendingFileRename_Count"] = $pendingRenameCount
        $details["PendingFileRename_Sample"] = $pendingRenameSample

        $activeName = ""
        $configuredName = ""

        try {
          $activeName = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ActiveComputerName" -Name "ComputerName" -ErrorAction Stop).ComputerName
        } catch {}

        try {
          $configuredName = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName" -Name "ComputerName" -ErrorAction Stop).ComputerName
        } catch {}

        $nameChangePending = $false
        if ($activeName -and $configuredName -and ($activeName -ne $configuredName)) {
          $nameChangePending = $true
          $reasons += "Eine Computername-Änderung wartet auf Neustart."
        }

        $details["ComputerName_Aktiv"] = $activeName
        $details["ComputerName_Konfiguriert"] = $configuredName
        $details["ComputerName_Aenderung_Ausstehend"] = $nameChangePending

        $ccmRebootPending = $null
        $ccmHardRebootPending = $null

        try {
          $ccm = Invoke-CimMethod -Namespace "root\ccm\ClientSDK" -ClassName "CCM_ClientUtilities" -MethodName "DetermineIfRebootPending" -ErrorAction Stop
          if ($ccm -and $ccm.ReturnValue -eq 0) {
            $ccmRebootPending = [bool]$ccm.RebootPending
            $ccmHardRebootPending = [bool]$ccm.IsHardRebootPending

            if ($ccmRebootPending -or $ccmHardRebootPending) {
              $reasons += "ConfigMgr/SCCM meldet einen ausstehenden Neustart."
            }
          }
        } catch {}

        $details["CCM_RebootPending"] = $ccmRebootPending
        $details["CCM_HardRebootPending"] = $ccmHardRebootPending

        $pending = ($reasons.Count -gt 0)

        [PSCustomObject]@{
          Reboot_Required = $pending
          Reason_Count    = $reasons.Count
          Reasons         = $reasons
          Details         = [PSCustomObject]$details
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    pending = bool(data.get("Reboot_Required", False))
    reason_count = int(data.get("Reason_Count", 0))
    reasons = ensure_list(data.get("Reasons", []))
    details = data.get("Details", {}) if isinstance(data, dict) else {}

    status = "ok"
    issues = []

    cbs_pending = bool(details.get("CBS_RebootPending", False))
    wu_pending = bool(details.get("WindowsUpdate_RebootRequired", False))
    update_exe_volatile = int(details.get("UpdateExeVolatile", 0) or 0)
    name_change_pending = bool(details.get("ComputerName_Aenderung_Ausstehend", False))
    ccm_pending = bool(details.get("CCM_RebootPending", False))
    ccm_hard_pending = bool(details.get("CCM_HardRebootPending", False))
    pending_rename_count = int(details.get("PendingFileRename_Count", 0) or 0)

    pending_rename_sample = ensure_list(details.get("PendingFileRename_Sample", []))
    pending_rename_text = " ".join(str(x).lower() for x in pending_rename_sample if x)

    hard_reboot_required = any([
        cbs_pending,
        wu_pending,
        update_exe_volatile != 0,
        ccm_pending,
        ccm_hard_pending,
    ])

    rename_only = (
        pending
        and pending_rename_count > 0
        and not hard_reboot_required
        and not name_change_pending
    )

    temp_like_rename_only = (
        rename_only
        and (
            "\\windows\\temp\\" in pending_rename_text
            or ".tmp" in pending_rename_text
            or "\\temp\\" in pending_rename_text
        )
    )

    name_change_only = (
        pending
        and name_change_pending
        and not hard_reboot_required
        and pending_rename_count == 0
    )

    if not pending:
        status = "ok"
        summary = "Kein ausstehender Neustart erkannt"

    elif hard_reboot_required:
        status = "critical"
        summary = f"Neustart dringend empfohlen | {reason_count} Ursache(n) erkannt"
        issues = reasons[:]

    elif name_change_only:
        status = "info"
        summary = "Neustart für Computername-Änderung ausstehend"
        issues = reasons[:]

    elif temp_like_rename_only:
        status = "warning"
        summary = "Neustarthinweis vorhanden | Ausstehende Datei-/Temp-Bereinigung erkannt"
        issues = [
            "PendingFileRenameOperations gefunden, aktuell aber kein Hinweis auf Windows Update / CBS / ConfigMgr.",
            "Wahrscheinlich werden temporäre Dateien oder ausstehende Dateioperationen beim nächsten Neustart bereinigt."
        ]
        issues.extend(reasons[:])

    elif rename_only:
        status = "warning"
        summary = "Neustarthinweis vorhanden | Ausstehende Datei-/Treiber-Operationen erkannt"
        issues = [
            "PendingFileRenameOperations gefunden, aber keine harte Neustartanforderung durch Windows Update / CBS / ConfigMgr."
        ]
        issues.extend(reasons[:])

    else:
        status = "warning"
        summary = f"Neustarthinweis vorhanden | {reason_count} Ursache(n) erkannt"
        issues = reasons[:]

    return make_result(
        "pending_reboot",
        "Neustartstatus",
        "Updates & Software",
        125,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_available_updates() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $queryError = ""
        $updates = @()

        try {
          $session = New-Object -ComObject Microsoft.Update.Session
          $searcher = $session.CreateUpdateSearcher()
          $result = $searcher.Search("IsInstalled=0 and IsHidden=0")

          foreach ($update in @($result.Updates)) {
            $categories = @()
            try {
              $categories = @($update.Categories | ForEach-Object { $_.Name } | Sort-Object -Unique)
            } catch {
              $categories = @()
            }

            $title = [string]$update.Title
            $titleLower = $title.ToLowerInvariant()
            $categoryText = ($categories -join ", ")
            $categoryLower = $categoryText.ToLowerInvariant()

            $kb = ""
            try {
              if ($update.KBArticleIDs -and $update.KBArticleIDs.Count -gt 0) {
                $kb = ($update.KBArticleIDs | ForEach-Object { "KB$_" }) -join ", "
              }
            } catch {
              $kb = ""
            }

            $severity = ""
            try {
              if ($update.MsrcSeverity) {
                $severity = [string]$update.MsrcSeverity
              }
            } catch {
              $severity = ""
            }

            $rebootBehavior = "Unbekannt"
            try {
              $rb = [int]$update.InstallationBehavior.RebootBehavior
              $rebootBehavior = switch ($rb) {
                0 { "Kein Neustart erwartet" }
                1 { "Neustart erforderlich" }
                2 { "Möglicherweise Neustart erforderlich" }
                default { "Unbekannt" }
              }
            } catch {
              $rebootBehavior = "Unbekannt"
            }

            $downloaded = $false
            try {
              $downloaded = [bool]$update.IsDownloaded
            } catch {}

            $browseOnly = $false
            try {
              $browseOnly = [bool]$update.BrowseOnly
            } catch {}

            $isSecurity = $false
            $isDefinition = $false
            $isDriver = $false
            $isOptional = $false

            if ($severity) {
              $isSecurity = $true
            }

            if ($titleLower -match "security|sicherheitsupdate" -or $categoryLower -match "security|sicherheit") {
              $isSecurity = $true
            }

            if ($titleLower -match "definition update|definitionsupdate" -or $categoryLower -match "definition") {
              $isDefinition = $true
            }

            if ($titleLower -match "driver|treiber" -or $categoryLower -match "driver|treiber") {
              $isDriver = $true
            }

            if ($browseOnly -or $titleLower -match "preview|vorschau") {
              $isOptional = $true
            }

            $updates += [PSCustomObject]@{
              Title          = $title
              KB             = $kb
              Categories     = $categoryText
              Severity       = $severity
              RebootBehavior = $rebootBehavior
              Downloaded     = $downloaded
              BrowseOnly     = $browseOnly
              IsSecurity     = $isSecurity
              IsDefinition   = $isDefinition
              IsDriver       = $isDriver
              IsOptional     = $isOptional
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        $securityCount = @($updates | Where-Object { $_.IsSecurity }).Count
        $definitionCount = @($updates | Where-Object { $_.IsDefinition }).Count
        $driverCount = @($updates | Where-Object { $_.IsDriver }).Count
        $optionalCount = @($updates | Where-Object { $_.IsOptional }).Count
        $rebootLikelyCount = @($updates | Where-Object { $_.RebootBehavior -ne "Kein Neustart erwartet" }).Count

        $regularCount = @(
          $updates | Where-Object {
            -not $_.IsSecurity -and
            -not $_.IsDefinition -and
            -not $_.IsDriver -and
            -not $_.IsOptional
          }
        ).Count

        [PSCustomObject]@{
          QuerySuccess              = [string]::IsNullOrWhiteSpace($queryError)
          QueryError                = $queryError
          Available_Update_Count    = @($updates).Count
          Security_Update_Count     = $securityCount
          Regular_Update_Count      = $regularCount
          Definition_Update_Count   = $definitionCount
          Driver_Update_Count       = $driverCount
          Optional_Update_Count     = $optionalCount
          RebootLikely_Update_Count = $rebootLikelyCount
          Updates                   = $updates | Select-Object Title, KB, Categories, Severity, RebootBehavior, Downloaded, BrowseOnly
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Windows-Update-Modul lieferte kein Dictionary zurück.")

    query_success = bool(data.get("QuerySuccess", False))
    query_error = str(data.get("QueryError", "") or "").strip()

    available_count = int(data.get("Available_Update_Count", 0) or 0)
    security_count = int(data.get("Security_Update_Count", 0) or 0)
    regular_count = int(data.get("Regular_Update_Count", 0) or 0)
    definition_count = int(data.get("Definition_Update_Count", 0) or 0)
    driver_count = int(data.get("Driver_Update_Count", 0) or 0)
    optional_count = int(data.get("Optional_Update_Count", 0) or 0)
    reboot_likely_count = int(data.get("RebootLikely_Update_Count", 0) or 0)

    status = "ok"
    issues: list[str] = []

    if not query_success:
        status = "warning"
        summary = report_tr("updates_query_unavailable")
        issues.append(f"Windows-Update-Abfrage fehlgeschlagen: {query_error or 'Unbekannter Fehler'}")
    elif available_count == 0:
        status = "ok"
        summary = report_tr("updates_none_available")
    elif security_count > 0 or regular_count > 0:
        status = "warning"
        summary = (
            report_tr("updates_available_fmt", count=available_count, security=security_count, regular=regular_count)
        )

        if security_count > 0:
            issues.append(report_tr("updates_security_issue_fmt", count=security_count))
        if regular_count > 0:
            issues.append(f"{regular_count} reguläre Update(s) verfügbar.")
        if reboot_likely_count > 0:
            issues.append(f"{reboot_likely_count} Update(s) können einen Neustart erfordern.")
    else:
        status = "info"
        summary = (
            f"{available_count} eher unkritische Update(s) verfügbar | "
            f"Definitionen: {definition_count} | Treiber: {driver_count} | Optional: {optional_count}"
        )

        if definition_count > 0:
            issues.append(f"{definition_count} Definitionsupdate(s) verfügbar.")
        if driver_count > 0:
            issues.append(f"{driver_count} Treiberupdate(s) verfügbar.")
        if optional_count > 0:
            issues.append(f"{optional_count} optionale/Vorschau-Update(s) verfügbar.")
        if reboot_likely_count > 0:
            issues.append(f"{reboot_likely_count} Update(s) können einen Neustart erfordern.")

    return make_result(
        "available_updates",
        "Verfügbare Windows-Updates",
        "Updates & Software",
        126,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_installed_software() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Normalize-InstallDate($value) {
          if ([string]::IsNullOrWhiteSpace($value)) {
            return ""
          }

          $text = [string]$value

          if ($text -match '^\d{8}$') {
            try {
              return ([datetime]::ParseExact($text, 'yyyyMMdd', $null)).ToString('yyyy-MM-dd')
            } catch {}
          }

          try {
            return (Get-Date $text).ToString('yyyy-MM-dd')
          } catch {}

          return $text
        }

        function Get-ProductCodeFromSubKey($subKeyName) {
          if ([string]::IsNullOrWhiteSpace($subKeyName)) {
            return ""
          }

          if ($subKeyName -match '^\{[0-9A-Fa-f\-]{36}\}$') {
            return $subKeyName.ToUpperInvariant()
          }

          if ($subKeyName -match '^[0-9A-Fa-f\-]{36}$') {
            return ("{" + $subKeyName.ToUpperInvariant() + "}")
          }

          return ""
        }

        function Get-SoftwareScore($item) {
          $score = 0

          if (-not [string]::IsNullOrWhiteSpace($item.ProductCode)) { $score += 10 }
          if (-not [string]::IsNullOrWhiteSpace($item.DisplayVersion)) { $score += 3 }
          if (-not [string]::IsNullOrWhiteSpace($item.Publisher)) { $score += 2 }
          if (-not [string]::IsNullOrWhiteSpace($item.InstallDate)) { $score += 2 }
          if (-not [string]::IsNullOrWhiteSpace($item.InstallLocation)) { $score += 2 }
          if (-not [string]::IsNullOrWhiteSpace([string]$item.EstimatedSizeMB)) { $score += 1 }

          return $score
        }

        function Get-UninstallEntries($registryView, $archLabel, $viewLabel) {
          $result = @()

          $baseKey = $null
          $uninstallKey = $null

          try {
            $baseKey = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
              [Microsoft.Win32.RegistryHive]::LocalMachine,
              $registryView
            )

            $uninstallKey = $baseKey.OpenSubKey("SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
            if ($null -eq $uninstallKey) {
              return @()
            }

            foreach ($subKeyName in $uninstallKey.GetSubKeyNames()) {
              $subKey = $null

              try {
                $subKey = $uninstallKey.OpenSubKey($subKeyName)
                if ($null -eq $subKey) { continue }

                $displayName = [string]$subKey.GetValue("DisplayName", "")
                if ([string]::IsNullOrWhiteSpace($displayName)) { continue }

                $displayVersion = [string]$subKey.GetValue("DisplayVersion", "")
                $publisher = [string]$subKey.GetValue("Publisher", "")
                $installDateRaw = [string]$subKey.GetValue("InstallDate", "")
                $installLocation = [string]$subKey.GetValue("InstallLocation", "")
                $releaseType = [string]$subKey.GetValue("ReleaseType", "")
                $parentKeyName = [string]$subKey.GetValue("ParentKeyName", "")

                $systemComponent = 0
                try {
                  $systemComponent = [int]$subKey.GetValue("SystemComponent", 0)
                } catch {
                  $systemComponent = 0
                }

                if ($systemComponent -eq 1) { continue }
                if (-not [string]::IsNullOrWhiteSpace($parentKeyName)) { continue }

                if ($releaseType -match 'Hotfix|Security Update|Update Rollup') { continue }
                if ($displayName -match '^(Update for|Security Update for|Hotfix for)\s') { continue }

                $estimatedSizeMB = ""
                try {
                  $estimatedSizeKB = $subKey.GetValue("EstimatedSize", $null)
                  if ($null -ne $estimatedSizeKB -and "$estimatedSizeKB" -ne "") {
                    $estimatedSizeMB = [math]::Round(([double]$estimatedSizeKB / 1024), 1)
                  }
                } catch {
                  $estimatedSizeMB = ""
                }

                $productCode = Get-ProductCodeFromSubKey $subKeyName

                $result += [PSCustomObject]@{
                  DisplayName     = $displayName
                  DisplayVersion  = $displayVersion
                  Publisher       = $publisher
                  InstallDate     = Normalize-InstallDate $installDateRaw
                  EstimatedSizeMB = $estimatedSizeMB
                  InstallLocation = $installLocation
                  Architecture    = $archLabel
                  RegistryHive    = $viewLabel
                  ProductCode     = $productCode
                  UninstallSubKey = $subKeyName
                }
              } finally {
                if ($null -ne $subKey) {
                  $subKey.Dispose()
                }
              }
            }
          } finally {
            if ($null -ne $uninstallKey) {
              $uninstallKey.Dispose()
            }
            if ($null -ne $baseKey) {
              $baseKey.Dispose()
            }
          }

          return $result
        }

        $queryError = ""
        $software = @()

        try {
          $software += Get-UninstallEntries ([Microsoft.Win32.RegistryView]::Registry64) "x64" "HKLM 64-Bit"
          $software += Get-UninstallEntries ([Microsoft.Win32.RegistryView]::Registry32) "x86" "HKLM 32-Bit"
        } catch {
          $queryError = $_.Exception.Message
        }

        $best = @{}
        $bestScore = @{}

        foreach ($item in $software) {
          $key = "{0}|{1}|{2}|{3}" -f $item.DisplayName, $item.DisplayVersion, $item.Publisher, $item.Architecture
          $score = Get-SoftwareScore $item

          if (-not $best.ContainsKey($key)) {
            $best[$key] = $item
            $bestScore[$key] = $score
          } elseif ($score -gt $bestScore[$key]) {
            $best[$key] = $item
            $bestScore[$key] = $score
          }
        }

        $deduped = @($best.Values | Sort-Object DisplayName, DisplayVersion, Publisher)

        $x64Count = @($deduped | Where-Object { $_.Architecture -eq "x64" }).Count
        $x86Count = @($deduped | Where-Object { $_.Architecture -eq "x86" }).Count
        $guidCount = @($deduped | Where-Object { -not [string]::IsNullOrWhiteSpace($_.ProductCode) }).Count

        [PSCustomObject]@{
          QuerySuccess             = [string]::IsNullOrWhiteSpace($queryError)
          QueryError               = $queryError
          Installed_Software_Count = @($deduped).Count
          x64_Count                = $x64Count
          x86_Count                = $x86Count
          GUID_Count               = $guidCount
          Software                 = $deduped
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Software-Modul lieferte kein Dictionary zurück.")

    query_success = bool(data.get("QuerySuccess", False))
    query_error = str(data.get("QueryError", "") or "").strip()
    software_count = int(data.get("Installed_Software_Count", 0) or 0)
    x64_count = int(data.get("x64_Count", 0) or 0)
    x86_count = int(data.get("x86_Count", 0) or 0)
    guid_count = int(data.get("GUID_Count", 0) or 0)

    status = "ok"
    issues: list[str] = []

    if not query_success:
        status = "warning"
        summary = "Software-Inventar konnte nicht vollständig gelesen werden"
        issues.append(f"Registry-Abfrage fehlgeschlagen: {query_error or 'Unbekannter Fehler'}")
    elif software_count == 0:
        status = "info"
        summary = "Keine installierte Software gefunden"
        issues.append("Es wurden keine verwertbaren Software-Einträge in den Uninstall-Keys gefunden.")
    elif software_count < 5:
        status = "info"
        summary = f"Nur wenige Software-Einträge gefunden | {software_count} Eintrag/Einträge"
        issues.append("Ungewöhnlich wenige Software-Einträge gefunden. Ergebnis ggf. prüfen.")
    else:
        status = "ok"
        summary = f"{software_count} Eintrag/Einträge | x64: {x64_count} | x86: {x86_count} | GUIDs: {guid_count}"

    return make_result(
        "installed_software",
        "Installierte Software",
        "Updates & Software",
        128,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_installed_updates() -> dict[str, Any]:
    data = powershell_json(
        r"""
        try {
          $updates = Get-HotFix |
            Select-Object `
              @{Name="Hotfix";Expression={$_.HotFixID}},
              @{Name="Beschreibung";Expression={$_.Description}},
              @{Name="Installiert_am";Expression={
                if ($_.InstalledOn) {
                  try { (Get-Date $_.InstalledOn).ToString("yyyy-MM-dd") } catch { "$($_.InstalledOn)" }
                } else {
                  ""
                }
              }} |
            Sort-Object Installiert_am -Descending

          $latestInstallDate = ""
          $last30 = 0
          $last90 = 0
          $today = Get-Date

          foreach ($u in $updates) {
            if (-not [string]::IsNullOrWhiteSpace($u.Installiert_am)) {
              if (-not $latestInstallDate) {
                $latestInstallDate = $u.Installiert_am
              }

              try {
                $d = Get-Date $u.Installiert_am
                $age = ($today - $d).Days

                if ($age -le 30) { $last30++ }
                if ($age -le 90) { $last90++ }
              } catch {}
            }
          }

          [PSCustomObject]@{
            Installed_Update_Count = @($updates).Count
            Latest_InstallDate     = $latestInstallDate
            Installed_Last_30_Days = $last30
            Installed_Last_90_Days = $last90
            Updates                = $updates
          } | ConvertTo-Json -Compress -Depth 5
        } catch {
          [PSCustomObject]@{
            Installed_Update_Count = 0
            Latest_InstallDate     = ""
            Installed_Last_30_Days = 0
            Installed_Last_90_Days = 0
            Updates                = @()
            QueryError             = $_.Exception.Message
          } | ConvertTo-Json -Compress -Depth 5
        }
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Installierte-Updates-Modul lieferte kein Dictionary zurück.")

    updates = ensure_list(data.get("Updates", []))
    latest_install_date = str(data.get("Latest_InstallDate", "") or "").strip()
    installed_last_30 = int(data.get("Installed_Last_30_Days", 0) or 0)
    installed_last_90 = int(data.get("Installed_Last_90_Days", 0) or 0)
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []
    update_age_days: int | None = None

    latest_date = parse_date_safe(latest_install_date)
    if latest_date:
        update_age_days = (dt.date.today() - latest_date).days

    data["Update_Age_Days"] = update_age_days

    if query_error:
        status = "warning"
        summary = "Installierte Updates konnten nicht vollständig gelesen werden"
        issues.append(f"Get-HotFix-Abfrage fehlgeschlagen: {query_error}")
    elif not updates:
        status = "warning"
        summary = "Keine installierten Updates erkannt"
        issues.append("Es wurden keine installierten Updates über Get-HotFix gefunden.")
    elif update_age_days is None:
        status = "info"
        summary = f"{len(updates)} installierte Update(s) gefunden | letztes Datum unklar"
        issues.append("Das Datum des zuletzt installierten Updates konnte nicht sauber bewertet werden.")
    elif update_age_days <= 30:
        status = "ok"
        summary = (
            f"Zuletzt installiert: {latest_install_date} | "
            f"30 Tage: {installed_last_30} | 90 Tage: {installed_last_90}"
        )
    elif update_age_days <= 45:
        status = "info"
        summary = (
            f"Zuletzt installiert: {latest_install_date} ({update_age_days} Tage) | "
            f"30 Tage: {installed_last_30} | 90 Tage: {installed_last_90}"
        )
        issues.append(f"Letztes erkanntes installiertes Update ist {update_age_days} Tage alt.")
    elif update_age_days <= 90:
        status = "warning"
        summary = (
            f"Zuletzt installiert: {latest_install_date} ({update_age_days} Tage) | "
            f"30 Tage: {installed_last_30} | 90 Tage: {installed_last_90}"
        )
        issues.append(f"Seit {update_age_days} Tagen kein aktuelles installiertes Update erkannt.")
    else:
        status = "critical"
        summary = (
            f"Zuletzt installiert: {latest_install_date} ({update_age_days} Tage) | "
            f"30 Tage: {installed_last_30} | 90 Tage: {installed_last_90}"
        )
        issues.append(f"Seit mehr als 90 Tagen kein aktuelles installiertes Update erkannt ({update_age_days} Tage).")

    return make_result(
        "installed_updates",
        "Installierte Updates",
        "Updates & Software",
        130,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )

def collect_module(
    title: str,
    func: Callable[[], dict[str, Any]],
    index: int,
    total: int,
    status_callback=None,
    progress_callback=None,
) -> dict[str, Any]:
    if status_callback:
        status_callback(tr("progress_reading").format(index=index, total=total, title=translate_title(title)))

    started = time.perf_counter()

    try:
        result = func()

        if result is None:
            raise RuntimeError("Modul hat kein Ergebnis zurückgegeben (None).")

        if not isinstance(result, dict):
            raise RuntimeError(f"Modul hat ungültigen Rückgabewert geliefert: {type(result).__name__}")

        result["duration_ms"] = int((time.perf_counter() - started) * 1000)

        if progress_callback:
            progress_callback(index, total)

        if status_callback:
            status_callback(
                f"[{index:02d}/{total:02d}] {title} abgeschlossen "
                f"({status_label(result['status'])})"
            )

        return result

    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)

        if progress_callback:
            progress_callback(index, total)

        if status_callback:
            status_callback(tr("progress_error").format(index=index, total=total, title=translate_title(title), error=localize_text(exc)))

        return make_result(
            module_id=title.lower().replace(" ", "_"),
            title=title,
            category="Inventar & Tiefeninfos",
            priority=999,
            result_type="text",
            data="",
            status="error",
            summary="Modul konnte nicht ausgeführt werden",
            issues=[str(exc)],
            error=str(exc),
            duration_ms=duration_ms,
        )

def collect_active_users() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            try {
              $lines = quser 2>$null
              if (-not $lines) {
                @([PSCustomObject]@{
                  UserName = ""
                  SessionName = ""
                  Id = ""
                  State = "Keine aktive Benutzersitzung gefunden"
                  IdleTime = ""
                  LogonTime = ""
                }) | ConvertTo-Json -Compress
                exit
              }

              $rows = @()
              foreach ($line in ($lines | Select-Object -Skip 1)) {
                $clean = ($line -replace '^\s*>?', '').Trim()
                if (-not $clean) { continue }

                $parts = $clean -split '\s{2,}'
                if ($parts.Count -ge 5) {
                  $rows += [PSCustomObject]@{
                    UserName    = $parts[0]
                    SessionName = $parts[1]
                    Id          = $parts[2]
                    State       = $parts[3]
                    IdleTime    = $parts[4]
                    LogonTime   = if ($parts.Count -ge 6) { ($parts[5..($parts.Count-1)] -join ' ') } else { "" }
                  }
                }
                elseif ($parts.Count -ge 4) {
                  $rows += [PSCustomObject]@{
                    UserName    = $parts[0]
                    SessionName = ""
                    Id          = $parts[1]
                    State       = $parts[2]
                    IdleTime    = $parts[3]
                    LogonTime   = if ($parts.Count -ge 5) { ($parts[4..($parts.Count-1)] -join ' ') } else { "" }
                  }
                }
              }

              if (-not $rows) {
                @([PSCustomObject]@{
                  UserName = ""
                  SessionName = ""
                  Id = ""
                  State = "Keine aktive Benutzersitzung gefunden"
                  IdleTime = ""
                  LogonTime = ""
                }) | ConvertTo-Json -Compress
              } else {
                $rows | ConvertTo-Json -Compress
              }
            } catch {
              @([PSCustomObject]@{
                UserName = ""
                SessionName = ""
                Id = ""
                State = "Abfrage fehlgeschlagen"
                IdleTime = ""
                LogonTime = $_.Exception.Message
              }) | ConvertTo-Json -Compress
            }
            """
        )
    )

    issues = []
    status = "ok"

    real_users = [
        row for row in data
        if str(row.get("State", "")).lower() not in {
            "keine aktive benutzersitzung gefunden",
            "abfrage fehlgeschlagen",
        }
    ]

    if real_users:
        status = "info"
        issues.append(f"{len(real_users)} aktive/r Benutzer/Sitzung(en) erkannt.")

    return make_result(
        "active_users",
        "Aktive Benutzer",
        "Benutzer & Last",
        140,
        "table",
        data,
        status=status,
        summary=f"{len(real_users)} aktive Sitzung(en)",
        issues=issues,
    )


def collect_top_processes() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $cpuTop = Get-Process |
          Sort-Object CPU -Descending |
          Select-Object -First 5 `
            Name,
            @{Name="CPU_Seconds";Expression={[math]::Round(($_.CPU), 2)}},
            Id

        $ramTop = Get-Process |
          Sort-Object WorkingSet -Descending |
          Select-Object -First 5 `
            Name,
            @{Name="RAM_MB";Expression={[math]::Round($_.WorkingSet / 1MB, 2)}},
            Id

        [PSCustomObject]@{
          CPU = $cpuTop
          RAM = $ramTop
        } | ConvertTo-Json -Compress -Depth 4
        """
    )

    cpu_top = ensure_list(data.get("CPU"))
    ram_top = ensure_list(data.get("RAM"))

    issues = []
    status = "ok"

    if ram_top:
        top_ram = float(ram_top[0].get("RAM_MB", 0))
        if top_ram >= 4096:
            status = "warning"
            issues.append(f"Sehr hoher RAM-Verbrauch beim Top-Prozess: {top_ram} MB")

    if cpu_top:
        top_cpu = float(cpu_top[0].get("CPU_Seconds", 0))
        if top_cpu >= 10000 and status != "warning":
            status = "info"
            issues.append(f"CPU-intensiver Prozess erkannt: {cpu_top[0].get('Name', '')}")

    return make_result(
        "top_processes",
        "Top-Prozesse",
        "Benutzer & Last",
        150,
        "sections",
        data,
        status=status,
        summary="Top 5 nach CPU und RAM",
        issues=issues,
    )


def collect_office() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $reg = "HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration"

        if (Test-Path $reg) {
          $o = Get-ItemProperty $reg

          $product = switch -Regex ($o.ProductReleaseIds) {
            "2019" { "MS Office 2019 Standard"; break }
            "2021" { "MS Office 2021 Standard"; break }
            "365"  { "Microsoft 365 Apps"; break }
            default { $o.ProductReleaseIds }
          }

          [PSCustomObject]@{
            Product = $product
            Version = $o.VersionToReport
            Source = "ClickToRun"
          } | ConvertTo-Json -Compress
        }
        else {
          [PSCustomObject]@{
            Product = "Office nicht gefunden"
            Version = "n/a"
            Source = "ClickToRun"
          } | ConvertTo-Json -Compress
        }
        """
    )

    status = "ok"
    issues = []

    if data.get("Product") == "Office nicht gefunden":
        status = "info"
        issues.append("Keine Click-to-Run-Office-Installation gefunden.")

    return make_result(
        "office",
        "Microsoft Office",
        "Updates & Software",
        160,
        "kv",
        data,
        status=status,
        summary=f"{data.get('Product', '')} | Version {data.get('Version', '')}",
        issues=issues,
    )


def collect_services() -> dict[str, Any]:
    raw_rows = ensure_list(
        powershell_json(
            r"""
            $computerSystem = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
            $operatingSystem = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
            $isServer = $false
            if ($operatingSystem) {
              $isServer = [int]$operatingSystem.ProductType -ne 1
            }
            $partOfDomain = $false
            $domainRole = 0
            if ($computerSystem) {
              $partOfDomain = [bool]$computerSystem.PartOfDomain
              $domainRole = [int]$computerSystem.DomainRole
            }
            $isDomainController = $domainRole -ge 4

            $serviceSpecs = @(
              @{ Name = "EventLog";     Severity = "critical"; Required = $true;  Expected = "Auto";          RoleHint = "Basis";      Note = "Windows-Ereignisprotokoll" },
              @{ Name = "Schedule";     Severity = "critical"; Required = $true;  Expected = "Auto";          RoleHint = "Basis";      Note = "Geplante Aufgaben" },
              @{ Name = "LanmanServer"; Severity = "critical"; Required = $true;  Expected = "Auto";          RoleHint = "Server";     Note = "Datei- und Druckfreigaben" },
              @{ Name = "RpcSs";        Severity = "critical"; Required = $true;  Expected = "Auto";          RoleHint = "Basis";      Note = "Remote Procedure Call" },
              @{ Name = "Winmgmt";      Severity = "warning";  Required = $true;  Expected = "Auto";          RoleHint = "Basis";      Note = "Windows-Verwaltungsinstrumentation" },
              @{ Name = "W32Time";      Severity = "warning";  Required = $false; Expected = $(if ($isServer -or $partOfDomain) { "Auto" } else { "ManualOrAuto" }); RoleHint = $(if ($isServer -or $partOfDomain) { "Server / Domäne" } else { "Optional" }); Note = "Zeitdienst" },
              @{ Name = "wuauserv";     Severity = "warning";  Required = $false; Expected = "ManualOrAuto";  RoleHint = "Basis";      Note = "Windows Update" },
              @{ Name = "TermService";  Severity = "warning";  Required = $false; Expected = "ManualOrAuto";  RoleHint = "Remotezugriff"; Note = "Remote Desktop Services" },
              @{ Name = "WinRM";        Severity = "warning";  Required = $false; Expected = $(if ($isServer) { "AutoIfPresent" } else { "ManualOrAuto" }); RoleHint = $(if ($isServer) { "Server" } else { "Optional" }); Note = "Windows Remote Management" },
              @{ Name = "Netlogon";     Severity = "warning";  Required = $false; Expected = $(if ($isDomainController) { "Auto" } elseif ($partOfDomain) { "ManualOrAuto" } else { "IgnoreIfWorkgroup" }); RoleHint = $(if ($isDomainController) { "Domain Controller" } elseif ($partOfDomain) { "Domänenmitglied" } else { "Arbeitsgruppe / Optional" }); Note = "Anmeldung / sichere Kanäle" },
              @{ Name = "Kdc";          Severity = "critical"; Required = $false; Expected = "AutoIfPresent"; RoleHint = "Domain Controller"; Note = "Kerberos Key Distribution Center" },
              @{ Name = "NTDS";         Severity = "critical"; Required = $false; Expected = "AutoIfPresent"; RoleHint = "Domain Controller"; Note = "Active Directory Domain Services" },
              @{ Name = "DFSR";         Severity = "warning";  Required = $false; Expected = "AutoIfPresent"; RoleHint = "Domain Controller"; Note = "Distributed File System Replication" },
              @{ Name = "DNS";          Severity = "warning";  Required = $false; Expected = "AutoIfPresent"; RoleHint = "Serverrolle"; Note = "DNS-Server" },
              @{ Name = "DHCPServer";   Severity = "warning";  Required = $false; Expected = "AutoIfPresent"; RoleHint = "Serverrolle"; Note = "DHCP-Server" },
              @{ Name = "W3SVC";        Severity = "warning";  Required = $false; Expected = "AutoIfPresent"; RoleHint = "Webserver"; Note = "IIS World Wide Web Publishing" }
            )

            function Get-ExpectedLabel([string]$expected) {
              switch ($expected) {
                "Auto"         { return "Automatisch" }
                "AutoIfPresent"{ return "Automatisch (wenn vorhanden)" }
                "ManualOrAuto"     { return "Manuell oder Automatisch" }
                "IgnoreIfWorkgroup"{ return "Nicht relevant bei Arbeitsgruppe" }
                default            { return $expected }
              }
            }

            function Get-FindingLabel([string]$severity) {
              switch ($severity) {
                "critical" { return "Kritisch" }
                "warning"  { return "Warnung" }
                "info"     { return "Hinweis" }
                default     { return "OK" }
              }
            }

            $rows = foreach ($spec in $serviceSpecs) {
              $name = [string]$spec.Name
              $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
              $cim = Get-CimInstance Win32_Service -Filter "Name='$name'" -ErrorAction SilentlyContinue

              $displayName = if ($svc -and $svc.DisplayName) { [string]$svc.DisplayName } else { $name }
              $status = if ($svc) { $svc.Status.ToString() } else { "Nicht vorhanden" }
              $startMode = if ($cim) { [string]$cim.StartMode } else { "n/a" }
              $expected = [string]$spec.Expected
              $ruleSeverity = [string]$spec.Severity
              $findingSeverity = "ok"
              $finding = "OK"
              $recommendation = "Keine Aktion erforderlich"

              if (-not $svc) {
                if ([bool]$spec.Required) {
                  $findingSeverity = $ruleSeverity
                  $finding = if ($ruleSeverity -eq "critical") { "Kritisch" } else { "Warnung" }
                  $recommendation = "Dienst prüfen oder Windows-Komponente reparieren"
                } else {
                  $findingSeverity = "ok"
                  $finding = "Nicht vorhanden"
                  $recommendation = "Nur relevant, wenn die zugehörige Serverrolle genutzt wird"
                }
              }
              else {
                if ($expected -in @("Auto", "AutoIfPresent")) {
                  if ($startMode -eq "Disabled") {
                    $findingSeverity = $ruleSeverity
                    $finding = Get-FindingLabel $ruleSeverity
                    $recommendation = "Starttyp auf Automatisch stellen und Dienststart prüfen"
                  }
                  elseif ($startMode -ne "Auto") {
                    $findingSeverity = if ($ruleSeverity -eq "critical") { "warning" } else { $ruleSeverity }
                    $finding = Get-FindingLabel $findingSeverity
                    $recommendation = "Starttyp auf Automatisch anpassen"
                  }
                  elseif ($status -ne "Running") {
                    $findingSeverity = $ruleSeverity
                    $finding = Get-FindingLabel $ruleSeverity
                    $recommendation = "Dienst starten und abhängige Fehler prüfen"
                  }
                }
                elseif ($expected -eq "ManualOrAuto") {
                  if ($startMode -eq "Disabled") {
                    $findingSeverity = "warning"
                    $finding = "Warnung"
                    $recommendation = "Deaktivierten Dienst nur bei bewusster Härtung beibehalten; sonst Starttyp prüfen"
                  }
                }
                elseif ($expected -eq "IgnoreIfWorkgroup") {
                  $findingSeverity = "ok"
                  $finding = "OK"
                  $recommendation = "Auf Arbeitsgruppen-Rechnern normalerweise kein Handlungsbedarf"
                }
              }

              [PSCustomObject]@{
                Name              = $name
                DisplayName       = $displayName
                Rolle             = [string]$spec.RoleHint
                Erwartet          = Get-ExpectedLabel $expected
                StartType         = $startMode
                Status            = $status
                Bewertung         = $finding
                Empfehlung        = $recommendation
                Hinweis           = [string]$spec.Note
                FindingSeverity   = $findingSeverity
                RuleSeverity      = $ruleSeverity
              }
            }

            $rows | ConvertTo-Json -Compress
            """
        )
    )

    status = "ok"
    issues: list[str] = []
    display_rows: list[dict[str, Any]] = []
    deviation_count = 0

    severity_order = {"critical": 4, "warning": 3, "info": 2, "ok": 1}

    for svc in raw_rows:
        finding_severity = str(svc.get("FindingSeverity", "ok") or "ok")
        display_row = {
            "Name": svc.get("Name", ""),
            "DisplayName": svc.get("DisplayName", ""),
            "Rolle": svc.get("Rolle", ""),
            "Erwartet": svc.get("Erwartet", ""),
            "StartType": svc.get("StartType", ""),
            "Status": svc.get("Status", ""),
            "Bewertung": svc.get("Bewertung", ""),
            "Empfehlung": svc.get("Empfehlung", ""),
            "Hinweis": svc.get("Hinweis", ""),
            "__row_status": finding_severity,
        }
        display_rows.append(display_row)

        if finding_severity != "ok":
            deviation_count += 1
            name = str(svc.get("Name", "") or "")
            display_name = str(svc.get("DisplayName", "") or name)
            expected = str(svc.get("Erwartet", "") or "")
            start_type = str(svc.get("StartType", "") or "")
            svc_status = str(svc.get("Status", "") or "")
            if finding_severity == "critical":
                status = "critical"
            elif finding_severity == "warning" and status != "critical":
                status = "warning"
            elif finding_severity == "info" and status not in {"critical", "warning"}:
                status = "info"
            if finding_severity in {"critical", "warning"}:
                issues.append(report_tr("analysis_service_mismatch", service=display_name, expected=localize_text(expected), start_type=localize_text(start_type), svc_status=localize_text(svc_status)))

    display_rows.sort(key=lambda row: severity_order.get(next((str(s.get('FindingSeverity', 'ok')) for s in raw_rows if s.get('Name') == row.get('Name')), 'ok'), 0), reverse=True)

    if deviation_count:
        summary = report_tr("services_summary_deviation", count=len(display_rows), deviations=deviation_count)
    else:
        summary = report_tr("services_summary_clean", count=len(display_rows))

    return make_result(
        "services",
        "Wichtige Dienste",
        "Sicherheit",
        170,
        "table",
        display_rows,
        status=status,
        summary=summary,
        issues=issues[:8],
    )


def collect_eventlogs() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            $start = (Get-Date).AddDays(-3)

            $events = Get-WinEvent -FilterHashtable @{
              LogName = @("System", "Application")
              StartTime = $start
              Level = @(1,2,3)
            } -ErrorAction SilentlyContinue |
            Sort-Object TimeCreated -Descending |
            Group-Object Id, ProviderName, LevelDisplayName |
            ForEach-Object { $_.Group | Select-Object -First 1 } |
            Select-Object -First 20 `
              @{Name="TimeCreated";Expression={$_.TimeCreated.ToString("yyyy-MM-dd HH:mm:ss")}},
              LogName,
              Id,
              LevelDisplayName,
              ProviderName,
              @{Name="Message";Expression={
                if ($_.Message) {
                  $msg = $_.Message -replace '\r?\n',' ' -replace '\s+',' '
                  if ($msg.Length -gt 350) {
                    $msg.Substring(0,350) + " ..."
                  } else {
                    $msg
                  }
                } else {
                  ""
                }
              }}

            $events | ConvertTo-Json -Compress
            """
        )
    )

    status = "ok"
    issues = []

    error_count = len([e for e in data if str(e.get("LevelDisplayName", "")).lower() in {"error", "kritisch", "critical"}])
    warning_count = len([e for e in data if str(e.get("LevelDisplayName", "")).lower() in {"warning", "warnung"}])

    if error_count >= 10:
        status = "critical"
        issues.append(f"Viele kritische/Fehler-Events in den letzten 3 Tagen: {error_count}")
    elif error_count > 0:
        status = "warning"
        issues.append(f"Fehler-Events in den letzten 3 Tagen: {error_count}")
    elif warning_count > 0:
        status = "info"
        issues.append(f"Warnungs-Events in den letzten 3 Tagen: {warning_count}")

    return make_result(
        "eventlogs",
        "Eventlog-Kurzcheck",
        "Inventar & Tiefeninfos",
        180,
        "table",
        data,
        status=status,
        summary=f"{len(data)} Event(s) aus System/Application der letzten 3 Tage",
        issues=issues,
    )


def collect_activation_status() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $queryError = ""
        $result = $null

        try {
          $windowsAppId = "55c92734-d682-4d71-983e-d6ec3f16059f"

          $product = Get-CimInstance SoftwareLicensingProduct -ErrorAction Stop |
            Where-Object {
              $_.ApplicationID -eq $windowsAppId -and
              $_.PartialProductKey -and
              $_.Name -match "Windows"
            } |
            Sort-Object LicenseStatus -Descending |
            Select-Object -First 1

          if ($null -eq $product) {
            $result = [PSCustomObject]@{
              QuerySuccess                = $true
              QueryError                  = ""
              ProductName                 = ""
              Activation_Status           = "Unbekannt"
              IsActivated                 = $false
              LicenseDescription          = ""
              LicenseChannel              = ""
              PartialProductKey           = ""
              GracePeriodRemaining_Minutes = 0
              GracePeriodRemaining_Days    = 0
            }
          } else {
            $statusText = switch ([int]$product.LicenseStatus) {
              0 { "Nicht lizenziert" }
              1 { "Lizenziert" }
              2 { "OOB Grace" }
              3 { "OOT Grace" }
              4 { "Non-Genuine Grace" }
              5 { "Benachrichtigung" }
              6 { "Extended Grace" }
              default { "Unbekannt" }
            }

            $channel = ""
            if ($product.Description -match "VOLUME_KMSCLIENT|VOLUME_MAK|RETAIL|OEM_DM|OEM_COA_NSLP|OEM_COA|OEM") {
              $channel = $matches[0]
            }

            $graceMinutes = 0
            try {
              $graceMinutes = [int]$product.GracePeriodRemaining
            } catch {
              $graceMinutes = 0
            }

            $result = [PSCustomObject]@{
              QuerySuccess                 = $true
              QueryError                   = ""
              ProductName                  = $product.Name
              Activation_Status            = $statusText
              IsActivated                  = ([int]$product.LicenseStatus -eq 1)
              LicenseDescription           = $product.Description
              LicenseChannel               = $channel
              PartialProductKey            = $product.PartialProductKey
              GracePeriodRemaining_Minutes = $graceMinutes
              GracePeriodRemaining_Days    = [math]::Round(($graceMinutes / 1440), 1)
            }
          }
        } catch {
          $queryError = $_.Exception.Message
          $result = [PSCustomObject]@{
            QuerySuccess                 = $false
            QueryError                   = $queryError
            ProductName                  = ""
            Activation_Status            = "Unbekannt"
            IsActivated                  = $false
            LicenseDescription           = ""
            LicenseChannel               = ""
            PartialProductKey            = ""
            GracePeriodRemaining_Minutes = 0
            GracePeriodRemaining_Days    = 0
          }
        }

        $result | ConvertTo-Json -Compress
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Aktivierungsmodul lieferte kein Dictionary zurück.")

    query_success = bool(data.get("QuerySuccess", False))
    is_activated = bool(data.get("IsActivated", False))
    product_name = str(data.get("ProductName", "") or "").strip()
    activation_status = str(data.get("Activation_Status", "") or "").strip()
    channel = str(data.get("LicenseChannel", "") or "").strip()
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if not query_success:
        status = "warning"
        summary = "Windows-Aktivierung konnte nicht gelesen werden"
        issues.append(f"Aktivierungsstatus konnte nicht ermittelt werden: {query_error or 'Unbekannter Fehler'}")
    elif not product_name:
        status = "info"
        summary = "Windows-Lizenzstatus nicht eindeutig ermittelbar"
    elif is_activated:
        status = "ok"
        summary = f"{activation_status} | {product_name}"
        if channel:
            summary += f" | {channel}"
    else:
        status = "warning"
        summary = f"{activation_status} | {product_name}"
        issues.append("Windows ist nicht als vollständig aktiviert erkannt.")

    return make_result(
        "activation_status",
        "Windows-Aktivierung",
        "Updates & Software",
        24,
        "kv",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_join_status() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Get-DsregValue($lines, $name) {
          foreach ($line in $lines) {
            if ($line -match "^\s*$name\s*:\s*(.+)$") {
              return $matches[1].Trim()
            }
          }
          return ""
        }

        function Convert-YesNoToBool($value) {
          if ([string]::IsNullOrWhiteSpace($value)) {
            return $null
          }
          return ($value.Trim().ToUpperInvariant() -eq "YES")
        }

        $queryError = ""
        $result = $null

        try {
          $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop

          $domainRoleText = switch ([int]$cs.DomainRole) {
            0 { "Standalone Workstation" }
            1 { "Member Workstation" }
            2 { "Standalone Server" }
            3 { "Member Server" }
            4 { "Backup Domain Controller" }
            5 { "Primary Domain Controller" }
            default { "Unbekannt" }
          }

          $dsregcmdAvailable = $false
          $azureAdJoined = $null
          $enterpriseJoined = $null
          $workplaceJoined = $null
          $tenantName = ""
          $deviceId = ""

          $dsregCmd = Get-Command dsregcmd.exe -ErrorAction SilentlyContinue
          if ($dsregCmd) {
            $dsregcmdAvailable = $true
            $dsregLines = & dsregcmd /status 2>$null

            $azureAdJoined = Convert-YesNoToBool (Get-DsregValue $dsregLines "AzureAdJoined")
            $enterpriseJoined = Convert-YesNoToBool (Get-DsregValue $dsregLines "EnterpriseJoined")
            $workplaceJoined = Convert-YesNoToBool (Get-DsregValue $dsregLines "WorkplaceJoined")
            $tenantName = Get-DsregValue $dsregLines "TenantName"
            $deviceId = Get-DsregValue $dsregLines "DeviceId"
          }

          $partOfDomain = [bool]$cs.PartOfDomain
          $hybridJoin = [bool]($partOfDomain -and $azureAdJoined)

          $result = [PSCustomObject]@{
            QuerySuccess     = $true
            QueryError       = ""
            PartOfDomain     = $partOfDomain
            Domain           = if ($partOfDomain) { $cs.Domain } else { "" }
            Workgroup        = if ($partOfDomain) { "" } else { $cs.Workgroup }
            DomainRoleText   = $domainRoleText
            AzureAdJoined    = $azureAdJoined
            EnterpriseJoined = $enterpriseJoined
            WorkplaceJoined  = $workplaceJoined
            HybridJoin       = $hybridJoin
            TenantName       = $tenantName
            DeviceId         = $deviceId
            DsregcmdAvailable = $dsregcmdAvailable
          }
        } catch {
          $queryError = $_.Exception.Message
          $result = [PSCustomObject]@{
            QuerySuccess      = $false
            QueryError        = $queryError
            PartOfDomain      = $false
            Domain            = ""
            Workgroup         = ""
            DomainRoleText    = "Unbekannt"
            AzureAdJoined     = $null
            EnterpriseJoined  = $null
            WorkplaceJoined   = $null
            HybridJoin        = $false
            TenantName        = ""
            DeviceId          = ""
            DsregcmdAvailable = $false
          }
        }

        $result | ConvertTo-Json -Compress
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Join-Status-Modul lieferte kein Dictionary zurück.")

    query_success = bool(data.get("QuerySuccess", False))
    query_error = str(data.get("QueryError", "") or "").strip()
    part_of_domain = bool(data.get("PartOfDomain", False))
    azure_ad_joined = data.get("AzureAdJoined")
    hybrid_join = bool(data.get("HybridJoin", False))
    domain = str(data.get("Domain", "") or "").strip()
    workgroup = str(data.get("Workgroup", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if not query_success:
        status = "warning"
        summary = "Join-Status konnte nicht gelesen werden"
        issues.append(f"Domänen-/Join-Status konnte nicht ermittelt werden: {query_error or 'Unbekannter Fehler'}")
    elif hybrid_join:
        status = "ok"
        summary = f"Hybrid Join | Domäne: {domain}"
    elif part_of_domain:
        status = "ok"
        summary = f"Domänenmitglied | {domain}"
    elif azure_ad_joined is True:
        status = "ok"
        summary = "Azure AD Joined"
    else:
        status = "info"
        summary = f"Kein Domain Join | Workgroup: {workgroup or 'unbekannt'}"

    return make_result(
        "join_status",
        "Join-Status",
        "Übersicht",
        25,
        "kv",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_remote_access() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Get-RegValueSafe($path, $name, $defaultValue) {
          try {
            return (Get-ItemProperty -Path $path -Name $name -ErrorAction Stop).$name
          } catch {
            return $defaultValue
          }
        }

        $rdpEnabled = ([int](Get-RegValueSafe "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" "fDenyTSConnections" 1) -eq 0)
        $nlaRequired = ([int](Get-RegValueSafe "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" "UserAuthentication" 0) -eq 1)
        $rdpPort = [int](Get-RegValueSafe "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" "PortNumber" 3389)

        $winrmServiceStatus = "Nicht gefunden"
        $winrmStartType = "n/a"
        $listenerCount = 0

        $svc = Get-Service WinRM -ErrorAction SilentlyContinue
        if ($svc) {
          $winrmServiceStatus = $svc.Status.ToString()
          try {
            $winrmStartType = (Get-CimInstance Win32_Service -Filter "Name='WinRM'" -ErrorAction Stop).StartMode
          } catch {
            $winrmStartType = "Unbekannt"
          }
        }

        try {
          $listenerCount = @(Get-ChildItem WSMan:\localhost\Listener -ErrorAction SilentlyContinue).Count
        } catch {
          $listenerCount = 0
        }

        [PSCustomObject]@{
          RDP_Enabled          = $rdpEnabled
          NLA_Required         = $nlaRequired
          RDP_Port             = $rdpPort
          WinRM_ServiceStatus  = $winrmServiceStatus
          WinRM_StartType      = $winrmStartType
          WinRM_ListenerCount  = $listenerCount
          PSRemotingAvailable  = ($listenerCount -gt 0)
        } | ConvertTo-Json -Compress
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Remote-Zugriff-Modul lieferte kein Dictionary zurück.")

    rdp_enabled = bool(data.get("RDP_Enabled", False))
    nla_required = bool(data.get("NLA_Required", False))
    winrm_status = str(data.get("WinRM_ServiceStatus", "") or "").strip()
    listener_count = int(data.get("WinRM_ListenerCount", 0) or 0)
    psremoting = bool(data.get("PSRemotingAvailable", False))

    status = "ok"
    issues: list[str] = []

    if rdp_enabled and not nla_required:
        status = "warning"
        summary = f"RDP aktiv ohne NLA | WinRM: {winrm_status}"
        issues.append("RDP ist aktiviert, aber NLA ist nicht erzwungen.")
    elif rdp_enabled:
        status = "ok"
        summary = f"RDP aktiv mit NLA | WinRM: {winrm_status}"
    elif psremoting or winrm_status == "Running":
        status = "ok"
        summary = f"RDP aus | WinRM aktiv ({listener_count} Listener)"
    else:
        status = "info"
        summary = "Keine aktiven Remotedienste erkannt"

    return make_result(
        "remote_access",
        "Remote-Zugriff",
        "Netzwerk",
        75,
        "kv",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_defender_signatures() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Get-RegValueSafe($path, $name, $defaultValue) {
          try {
            return (Get-ItemProperty -Path $path -Name $name -ErrorAction Stop).$name
          } catch {
            return $defaultValue
          }
        }

        function Normalize-Version($value) {
          $text = [string]$value
          if (-not $text) { return "" }
          if ($text -eq "0.0.0.0") { return "" }
          return $text
        }

        $mpCmd = Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue

        if (-not $mpCmd) {
          [PSCustomObject]@{
            QuerySuccess                  = $true
            QueryError                    = ""
            DefenderAvailable             = $false
            AntivirusEnabled              = $null
            RealTimeProtectionEnabled     = $null
            AntivirusSignatureVersion     = ""
            AntivirusSignatureLastUpdated = ""
            SignatureAgeDays              = $null
            AMEngineVersion               = ""
            NISSignatureVersion           = ""
            NISSignatureLastUpdated       = ""
            NISSignatureAgeDays           = $null
          } | ConvertTo-Json -Compress
          return
        }

        try {
          $mp = Get-MpComputerStatus

          $sigAgeDays = $null
          if ($mp.AntivirusSignatureLastUpdated) {
            $sigAgeDays = [int][math]::Floor(((Get-Date) - $mp.AntivirusSignatureLastUpdated).TotalDays)
          }

          $nisAgeDays = $null
          if ($mp.NISSignatureLastUpdated) {
            $nisAgeDays = [int][math]::Floor(((Get-Date) - $mp.NISSignatureLastUpdated).TotalDays)
          }

          $engineVersion = Normalize-Version $mp.AMEngineVersion
          if (-not $engineVersion) {
            $engineVersion = Normalize-Version (Get-RegValueSafe "HKLM:\SOFTWARE\Microsoft\Windows Defender\Signature Updates" "EngineVersion" "")
          }
          if (-not $engineVersion) {
            $engineVersion = Normalize-Version (Get-RegValueSafe "HKLM:\SOFTWARE\Microsoft\Windows Defender" "EngineVersion" "")
          }

          [PSCustomObject]@{
            QuerySuccess                  = $true
            QueryError                    = ""
            DefenderAvailable             = $true
            AntivirusEnabled              = $mp.AntivirusEnabled
            RealTimeProtectionEnabled     = $mp.RealTimeProtectionEnabled
            AntivirusSignatureVersion     = $mp.AntivirusSignatureVersion
            AntivirusSignatureLastUpdated = if ($mp.AntivirusSignatureLastUpdated) { $mp.AntivirusSignatureLastUpdated.ToString("yyyy-MM-dd HH:mm:ss") } else { "" }
            SignatureAgeDays              = $sigAgeDays
            AMEngineVersion               = $engineVersion
            NISSignatureVersion           = $mp.NISSignatureVersion
            NISSignatureLastUpdated       = if ($mp.NISSignatureLastUpdated) { $mp.NISSignatureLastUpdated.ToString("yyyy-MM-dd HH:mm:ss") } else { "" }
            NISSignatureAgeDays           = $nisAgeDays
          } | ConvertTo-Json -Compress
        } catch {
          [PSCustomObject]@{
            QuerySuccess                  = $false
            QueryError                    = $_.Exception.Message
            DefenderAvailable             = $true
            AntivirusEnabled              = $null
            RealTimeProtectionEnabled     = $null
            AntivirusSignatureVersion     = ""
            AntivirusSignatureLastUpdated = ""
            SignatureAgeDays              = $null
            AMEngineVersion               = ""
            NISSignatureVersion           = ""
            NISSignatureLastUpdated       = ""
            NISSignatureAgeDays           = $null
          } | ConvertTo-Json -Compress
        }
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Defender-Signaturmodul lieferte kein Dictionary zurück.")

    query_success = bool(data.get("QuerySuccess", False))
    defender_available = bool(data.get("DefenderAvailable", False))
    query_error = str(data.get("QueryError", "") or "").strip()
    av_enabled = data.get("AntivirusEnabled")
    rtp_enabled = data.get("RealTimeProtectionEnabled")
    sig_age_days = data.get("SignatureAgeDays")
    engine_version = str(data.get("AMEngineVersion", "") or "").strip()

    if engine_version == "0.0.0.0":
        data["AMEngineVersion"] = ""
        engine_version = ""

    status = "ok"
    issues: list[str] = []

    if not defender_available:
        status = "info"
        summary = report_tr("defender_cmdlets_unavailable")
    elif not query_success:
        status = "warning"
        summary = report_tr("defender_signature_status_unreadable")
        issues.append(report_tr("defender_signature_status_error_fmt", error=(query_error or "Unbekannter Fehler")))
    elif av_enabled is not True or rtp_enabled is not True:
        status = "info"
        summary = report_tr("defender_not_primary")
    elif sig_age_days is None:
        status = "info"
        summary = report_tr("defender_active_signature_age_unknown")
    else:
        sig_age_days = int(sig_age_days)
        if sig_age_days <= 3:
            status = "ok"
        elif sig_age_days <= 7:
            status = "info"
        elif sig_age_days <= 14:
            status = "warning"
            issues.append(f"Defender-Signaturen sind {sig_age_days} Tage alt.")
        else:
            status = "critical"
            issues.append(f"Defender-Signaturen sind stark veraltet ({sig_age_days} Tage).")

        summary = f"Defender-Signaturen {sig_age_days} Tage alt"

    return make_result(
        "defender_signatures",
        "Defender-Signaturen",
        "Sicherheit",
        95,
        "kv",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_time_service() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Get-RegValueSafe($path, $name, $defaultValue) {
          try {
            return (Get-ItemProperty -Path $path -Name $name -ErrorAction Stop).$name
          } catch {
            return $defaultValue
          }
        }

        $svc = Get-Service W32Time -ErrorAction SilentlyContinue
        $serviceStatus = if ($svc) { $svc.Status.ToString() } else { "Nicht gefunden" }

        $startType = "n/a"
        try {
          $startType = (Get-CimInstance Win32_Service -Filter "Name='W32Time'" -ErrorAction Stop).StartMode
        } catch {
          $startType = "Unbekannt"
        }

        $timeType = [string](Get-RegValueSafe "HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters" "Type" "")
        $ntpServer = [string](Get-RegValueSafe "HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters" "NtpServer" "")

        $timeSource = ""
        $timeSourceError = ""
        try {
          $w32tmOutput = & w32tm /query /source 2>&1
          $rawSource = ($w32tmOutput | Out-String).Trim()
          if ($LASTEXITCODE -ne 0) {
            $timeSourceError = $rawSource
          } else {
            $timeSource = $rawSource
            if ($timeSource -match "Folgender Fehler ist aufgetreten:") {
              $timeSourceError = $timeSource
              $timeSource = ""
            }
          }
        } catch {
          $timeSourceError = $_.Exception.Message
          $timeSource = ""
        }

        $tz = Get-TimeZone
        $nowLocal = Get-Date
        $nowUtc = (Get-Date).ToUniversalTime()

        $offset = ""
        try {
          $offset = [System.TimeZoneInfo]::Local.GetUtcOffset($nowLocal).ToString()
        } catch {}

        [PSCustomObject]@{
          W32Time_ServiceStatus = $serviceStatus
          W32Time_StartType     = $startType
          TimeServiceType       = $timeType
          NtpServer             = $ntpServer
          TimeSource            = $timeSource
          TimeSourceError       = $timeSourceError
          TimeZoneId            = $tz.Id
          TimeZoneName          = $tz.DisplayName
          LocalDateTime         = $nowLocal.ToString("dddd, dd.MM.yyyy HH:mm:ss")
          UtcDateTime           = $nowUtc.ToString("yyyy-MM-dd HH:mm:ss 'UTC'")
          TimeZoneOffset        = $offset
        } | ConvertTo-Json -Compress
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Zeitdienst-Modul lieferte kein Dictionary zurück.")

    service_status = str(data.get("W32Time_ServiceStatus", "") or "").strip()
    time_type = str(data.get("TimeServiceType", "") or "").strip()
    time_source = str(data.get("TimeSource", "") or "").strip()
    time_source_error = str(data.get("TimeSourceError", "") or "").strip()
    local_time = str(data.get("LocalDateTime", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    access_denied_time_source = (
        service_status == "Running"
        and bool(local_time)
        and bool(time_source_error)
        and (
            "0x80070005" in time_source_error
            or "zugriff verweigert" in time_source_error.lower()
            or "access is denied" in time_source_error.lower()
            or "access denied" in time_source_error.lower()
        )
    )

    if access_denied_time_source:
        data["TimeSourceError"] = ""
        status = "ok"
        summary = f"Zeitdienst aktiv | Typ: {time_type or 'unbekannt'}"
        if local_time:
            summary += f" | Lokal: {local_time}"
    else:
        source_lower = time_source.lower()

        if service_status != "Running":
            status = "warning"
            summary = f"Zeitdienst nicht aktiv | Status: {service_status}"
            if local_time:
                summary += f" | Lokal: {local_time}"
            issues.append("Der Windows-Zeitdienst läuft nicht.")
        elif time_source_error:
            status = "info"
            summary = f"Zeitdienst aktiv | Typ: {time_type or 'unbekannt'} | Quelle nicht lesbar"
            if local_time:
                summary += f" | Lokal: {local_time}"
            issues.append(f"Zeitquelle konnte nicht direkt abgefragt werden: {time_source_error}")
        elif not time_source:
            status = "info"
            summary = f"Zeitdienst aktiv | Typ: {time_type or 'unbekannt'} | Quelle unklar"
            if local_time:
                summary += f" | Lokal: {local_time}"
        elif "local cmos clock" in source_lower or "free-running system clock" in source_lower or "freilauf" in source_lower:
            status = "warning"
            summary = f"Zeitquelle lokal/ungenau | Quelle: {time_source}"
            if local_time:
                summary += f" | Lokal: {local_time}"
            issues.append(f"Zeitquelle ist nicht sauber synchronisiert: {time_source}")
        elif "vm ic time synchronization provider" in source_lower:
            status = "info"
            summary = f"Zeitquelle über Hypervisor | Quelle: {time_source}"
            if local_time:
                summary += f" | Lokal: {local_time}"
        else:
            status = "ok"
            summary = f"Zeitquelle: {time_source} | Typ: {time_type or 'unbekannt'}"
            if local_time:
                summary += f" | Lokal: {local_time}"

    return make_result(
        "time_service",
        "Zeitdienst / NTP",
        "Netzwerk",
        78,
        "kv",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )

def collect_shares() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Clean-String($value) {
          if ($null -eq $value) { return "" }
          return ([string]$value).Trim()
        }

        function Is-HiddenShare($name) {
          return ([string]$name).Trim().EndsWith('$')
        }

        function Has-Cmd($name) {
          return [bool](Get-Command $name -ErrorAction SilentlyContinue)
        }

        $rows = @()
        $queryMode = ""
        $queryError = ""
        $totalCount = 0
        $adminCount = 0
        $riskyCount = 0
        $primarySuccess = $false

        if (Has-Cmd "Get-SmbShare") {
          try {
            $queryMode = "Get-SmbShare"
            $primarySuccess = $true

            foreach ($share in @(Get-SmbShare -ErrorAction Stop)) {
              $name = Clean-String $share.Name
              if (-not $name -or $name -eq "IPC$") { continue }

              $totalCount++

              if (Is-HiddenShare $name) {
                $adminCount++
                continue
              }

              $path = Clean-String $share.Path
              $desc = Clean-String $share.Description
              $shareType = if ($share.Special) { "Spezial" } else { "Standard" }

              $accessSummary = ""
              $riskyAccess = $false
              $finding = ""

              if (Has-Cmd "Get-SmbShareAccess") {
                try {
                  $rules = @(
                    Get-SmbShareAccess -Name $name -ErrorAction Stop |
                    Where-Object { $_.AccessControlType -eq "Allow" }
                  )

                  if ($rules) {
                    $accessSummary = (
                      $rules |
                      ForEach-Object { "{0} ({1})" -f $_.AccountName, $_.AccessRight } |
                      Sort-Object -Unique |
                      Select-Object -First 6
                    ) -join ", "
                  }

                  foreach ($rule in $rules) {
                    $acct = ([string]$rule.AccountName).ToLowerInvariant()
                    $right = [string]$rule.AccessRight

                    if (
                      ($acct -in @("everyone", "gäste", "guests", "authenticated users", "authentifizierte benutzer")) -and
                      ($right -in @("Full", "Change"))
                    ) {
                      $riskyAccess = $true
                    }
                  }
                } catch {}
              }

              if ($riskyAccess) {
                $riskyCount++
                $finding = "Breite Freigabeberechtigung"
              }

              $rows += [PSCustomObject]@{
                ShareName     = $name
                Path          = $path
                Beschreibung  = $desc
                ShareType     = $shareType
                AccessSummary = $accessSummary
                RiskyAccess   = $riskyAccess
                Auffaelligkeit = $finding
              }
            }
          } catch {
            $queryError = $_.Exception.Message
            $primarySuccess = $false
          }
        }

        if (-not $primarySuccess) {
          try {
            $queryMode = if ($queryMode) { $queryMode + " / Win32_Share" } else { "Win32_Share" }
            $rows = @()
            $totalCount = 0
            $adminCount = 0
            $riskyCount = 0

            foreach ($share in @(Get-CimInstance Win32_Share -ErrorAction Stop)) {
              $name = Clean-String $share.Name
              if (-not $name -or $name -eq "IPC$") { continue }

              $totalCount++

              if (Is-HiddenShare $name) {
                $adminCount++
                continue
              }

              $shareType = switch ([int]$share.Type) {
                0 { "Datenträger" }
                1 { "Drucker" }
                2 { "Gerät" }
                3 { "IPC" }
                default { "Unbekannt" }
              }

              $rows += [PSCustomObject]@{
                ShareName      = $name
                Path           = Clean-String $share.Path
                Beschreibung   = Clean-String $share.Description
                ShareType      = $shareType
                AccessSummary  = "Nicht geprüft (WMI-Fallback)"
                RiskyAccess    = $null
                Auffaelligkeit = ""
              }
            }
          } catch {
            if (-not $queryError) {
              $queryError = $_.Exception.Message
            }
          }
        }

        [PSCustomObject]@{
          QueryMode          = $queryMode
          QueryError         = $queryError
          Share_Count_Total  = $totalCount
          Share_Count_Visible = @($rows).Count
          AdminShare_Count   = $adminCount
          Risky_Share_Count  = $riskyCount
          Shares             = @($rows | Sort-Object ShareName)
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("SMB-Freigaben-Modul lieferte kein Dictionary zurück.")

    visible_count = int(data.get("Share_Count_Visible", 0) or 0)
    total_count = int(data.get("Share_Count_Total", 0) or 0)
    admin_count = int(data.get("AdminShare_Count", 0) or 0)
    risky_count = int(data.get("Risky_Share_Count", 0) or 0)
    query_mode = str(data.get("QueryMode", "") or "").strip()
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if total_count == 0 and query_error:
        status = "warning"
        summary = "Freigaben konnten nicht ermittelt werden"
        issues.append(f"SMB-/Share-Abfrage fehlgeschlagen: {query_error}")
    elif risky_count > 0:
        status = "warning"
        summary = f"{visible_count} sichtbare Freigabe(n) | auffällig: {risky_count}"
        issues.append(f"{risky_count} Freigabe(n) mit potenziell breiten Berechtigungen erkannt.")
    elif visible_count > 0:
        status = "info"
        summary = f"{visible_count} benutzerdefinierte Freigabe(n) | Admin-Freigaben ausgeblendet: {admin_count}"
        issues.append(f"{visible_count} sichtbare Freigabe(n) vorhanden.")
    else:
        status = "ok"
        summary = f"Keine benutzerdefinierten Freigaben sichtbar | Admin-Freigaben: {admin_count}"

    if query_mode and "Win32_Share" in query_mode and status == "ok":
        status = "info"
        issues.append("Freigaben wurden per WMI-Fallback ermittelt; Berechtigungen konnten nicht vollständig geprüft werden.")

    return make_result(
        "shares",
        "Freigegebene Ordner / SMB-Basischeck",
        "Netzwerk",
        72,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_local_admins() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Resolve-GroupNameFromSid($sidText) {
          try {
            $sid = New-Object System.Security.Principal.SecurityIdentifier($sidText)
            $account = $sid.Translate([System.Security.Principal.NTAccount]).Value
            return ($account -split '\\')[-1]
          } catch {
            return ""
          }
        }

        function Get-MemberValue($member, $propertyName) {
          try {
            return $member.GetType().InvokeMember($propertyName, 'GetProperty', $null, $member, $null)
          } catch {
            return ""
          }
        }

        function Get-LocalGroupMembersBySid($sidText) {
          $groupName = Resolve-GroupNameFromSid $sidText

          if (-not $groupName) {
            return [PSCustomObject]@{
              Count   = 0
              Members = @()
              Error   = "Gruppe für SID $sidText konnte nicht aufgelöst werden."
            }
          }

          try {
            $group = [ADSI]("WinNT://./" + $groupName + ",group")
            $members = @()

            foreach ($member in @($group.psbase.Invoke("Members"))) {
              $adsPath = [string](Get-MemberValue $member "ADsPath")
              $name = [string](Get-MemberValue $member "Name")
              $objectClass = [string](Get-MemberValue $member "Class")
              $source = ""

              if ($adsPath -match '^WinNT://([^/]+)/') {
                $source = $matches[1]
              }

              $members += [PSCustomObject]@{
                Name        = $name
                ObjectClass = $objectClass
                Source      = $source
                ADSPath     = $adsPath
              }
            }

            return [PSCustomObject]@{
              Count   = @($members).Count
              Members = @($members | Sort-Object Source, Name)
              Error   = ""
            }
          } catch {
            return [PSCustomObject]@{
              Count   = 0
              Members = @()
              Error   = $_.Exception.Message
            }
          }
        }

        $admins = Get-LocalGroupMembersBySid "S-1-5-32-544"
        $rdpUsers = Get-LocalGroupMembersBySid "S-1-5-32-555"
        $backupOps = Get-LocalGroupMembersBySid "S-1-5-32-551"

        $errors = @()
        foreach ($e in @($admins.Error, $rdpUsers.Error, $backupOps.Error)) {
          if (-not [string]::IsNullOrWhiteSpace($e)) {
            $errors += $e
          }
        }

        [PSCustomObject]@{
          QueryError                = ($errors -join " | ")
          Administrators_Count      = [int]$admins.Count
          RemoteDesktopUsers_Count  = [int]$rdpUsers.Count
          BackupOperators_Count     = [int]$backupOps.Count
          Administrators            = $admins.Members
          RemoteDesktopUsers        = $rdpUsers.Members
          BackupOperators           = $backupOps.Members
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Lokale-Administratoren-Modul lieferte kein Dictionary zurück.")

    admins_count = int(data.get("Administrators_Count", 0) or 0)
    rdp_count = int(data.get("RemoteDesktopUsers_Count", 0) or 0)
    backup_count = int(data.get("BackupOperators_Count", 0) or 0)
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if query_error and admins_count == 0 and rdp_count == 0 and backup_count == 0:
        status = "warning"
        summary = "Privilegierte Gruppen konnten nicht gelesen werden"
        issues.append(f"Gruppenabfrage fehlgeschlagen: {query_error}")
    else:
        summary = f"Admins: {admins_count} | RDP-Benutzer: {rdp_count} | Backup Operators: {backup_count}"

        if admins_count > 2 or rdp_count > 0 or backup_count > 0:
            status = "info"

        if admins_count > 2:
            issues.append(f"Lokale Administratoren haben {admins_count} Mitglied(er).")
        if rdp_count > 0:
            issues.append(f"{rdp_count} Mitglied(er) in 'Remote Desktop Users'.")
        if backup_count > 0:
            issues.append(f"{backup_count} Mitglied(er) in 'Backup Operators'.")
        if query_error:
            status = "info" if status == "ok" else status
            issues.append(f"Teilweise unvollständige Gruppenabfrage: {query_error}")

    return make_result(
        "local_admins",
        "Lokale Administratoren / privilegierte Gruppen",
        "Sicherheit",
        171,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_scheduled_tasks() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Format-DateSafe($value) {
          try {
            if ($null -eq $value) { return "" }
            $dt = [datetime]$value
            if ($dt.Year -lt 2000) { return "" }
            return $dt.ToString("yyyy-MM-dd HH:mm:ss")
          } catch {
            return ""
          }
        }

        function Convert-TaskResultText($code) {
          if ($null -eq $code -or "$code" -eq "") { return "" }

          $num = [int64]$code
          switch ($num) {
            0 { return "Erfolgreich" }
            267008 { return "Bereit" }
            267009 { return "Wird ausgeführt" }
            267010 { return "Deaktiviert" }
            267011 { return "Noch nicht gestartet" }
            267012 { return "Keine Trigger / keine weiteren Läufe" }
            267013 { return "Beendet" }
            default { return ("0x{0:X8}" -f $num) }
          }
        }

        $rows = @()
        $queryError = ""
        $ignoreCodes = @(0, 267008, 267009, 267010, 267011, 267012, 267013)

        try {
          foreach ($task in @(Get-ScheduledTask -ErrorAction Stop)) {
            $taskName = [string]$task.TaskName
            $taskPath = [string]$task.TaskPath
            $state = [string]$task.State
            $enabled = $true
            $isMicrosoftTask = $taskPath -like "\Microsoft\*"

            try {
              $enabled = [bool]$task.Settings.Enabled
            } catch {
              $enabled = $true
            }

            $lastRunTime = ""
            $nextRunTime = ""
            $lastTaskResult = $null
            $lastRunAgeDays = $null

            try {
              $info = $task | Get-ScheduledTaskInfo -ErrorAction Stop
              $lastRunTime = Format-DateSafe $info.LastRunTime
              $nextRunTime = Format-DateSafe $info.NextRunTime
              $lastTaskResult = [int64]$info.LastTaskResult

              if ($lastRunTime) {
                try {
                  $lastRunAgeDays = [int]((Get-Date) - [datetime]$lastRunTime).TotalDays
                } catch {}
              }
            } catch {}

            $issueType = ""

            if (-not $enabled -and -not $isMicrosoftTask) {
              $issueType = "Deaktiviert"
            }
            elseif (
              $null -ne $lastTaskResult -and
              ($ignoreCodes -notcontains [int64]$lastTaskResult) -and
              $lastRunAgeDays -ne $null -and
              $lastRunAgeDays -le 30
            ) {
              $issueType = "Fehler bei letzter Ausführung"
            }

            if ($issueType) {
              $rows += [PSCustomObject]@{
                TaskName       = $taskName
                TaskPath       = $taskPath
                State          = $state
                Enabled        = $enabled
                LastRunTime    = $lastRunTime
                NextRunTime    = $nextRunTime
                LastTaskResult = if ($null -ne $lastTaskResult) { $lastTaskResult } else { "" }
                ResultText     = Convert-TaskResultText $lastTaskResult
                IssueType      = $issueType
                IsMicrosoftTask = $isMicrosoftTask
              }
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        $sortedRows = @(
          $rows |
          Sort-Object `
            @{Expression={ if ($_.IssueType -eq "Fehler bei letzter Ausführung") { 0 } else { 1 } }},
            TaskPath,
            TaskName |
          Select-Object -First 60
        )

        [PSCustomObject]@{
          QueryError                 = $queryError
          Suspicious_Task_Count      = @($rows).Count
          Windows_Task_Count         = @($rows | Where-Object { $_.IsMicrosoftTask }).Count
          Windows_Failed_Task_Count  = @($rows | Where-Object { $_.IsMicrosoftTask -and $_.IssueType -eq "Fehler bei letzter Ausführung" }).Count
          Custom_Task_Count          = @($rows | Where-Object { -not $_.IsMicrosoftTask }).Count
          Custom_Failed_Task_Count   = @($rows | Where-Object { -not $_.IsMicrosoftTask -and $_.IssueType -eq "Fehler bei letzter Ausführung" }).Count
          Disabled_Custom_Task_Count = @($rows | Where-Object { -not $_.IsMicrosoftTask -and $_.IssueType -eq "Deaktiviert" }).Count
          Tasks                      = $sortedRows
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Scheduled-Tasks-Modul lieferte kein Dictionary zurück.")

    suspicious_count = int(data.get("Suspicious_Task_Count", 0) or 0)
    windows_task_count = int(data.get("Windows_Task_Count", 0) or 0)
    windows_failed_count = int(data.get("Windows_Failed_Task_Count", 0) or 0)
    custom_task_count = int(data.get("Custom_Task_Count", 0) or 0)
    custom_failed_count = int(data.get("Custom_Failed_Task_Count", 0) or 0)
    disabled_custom_count = int(data.get("Disabled_Custom_Task_Count", 0) or 0)
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if suspicious_count == 0 and query_error:
        status = "warning"
        summary = "Geplante Tasks konnten nicht geprüft werden"
        issues.append(f"Task-Abfrage fehlgeschlagen: {query_error}")

    elif custom_failed_count > 0:
        status = "warning"
        summary = (
            f"Eigene auffällig: {custom_task_count} | "
            f"Fehler: {custom_failed_count} | "
            f"Deaktiviert: {disabled_custom_count}"
        )
        if windows_task_count > 0:
            summary += f" | Windows-Hinweise: {windows_task_count}"

        issues.append(f"{custom_failed_count} eigene / Drittanbieter-Task(s) mit Fehlerstatus erkannt.")
        if disabled_custom_count > 0:
            issues.append(f"{disabled_custom_count} deaktivierte eigene / Drittanbieter-Task(s) erkannt.")
        if windows_failed_count > 0:
            issues.append(f"{windows_failed_count} auffällige Windows-Task(s) nur als Hinweis erfasst.")

    elif disabled_custom_count > 0:
        status = "info"
        summary = f"Eigene deaktiviert: {disabled_custom_count}"
        if windows_task_count > 0:
            summary += f" | Windows-Hinweise: {windows_task_count}"

        issues.append(f"{disabled_custom_count} deaktivierte eigene / Drittanbieter-Task(s) erkannt.")
        if windows_failed_count > 0:
            issues.append(f"{windows_failed_count} auffällige Windows-Task(s) nur als Hinweis erfasst.")

    elif windows_task_count > 0:
        status = "info"
        summary = f"Windows-Hinweise: {windows_task_count}"
        if windows_failed_count > 0:
            issues.append(f"{windows_failed_count} auffällige Windows-Task(s) nur als Hinweis erfasst.")

    else:
        status = "ok"
        summary = "Keine auffälligen geplanten Tasks erkannt"

    if query_error and status in {"ok", "info"}:
        status = "info"
        issues.append(f"Teilweise unvollständige Task-Abfrage: {query_error}")

    return make_result(
        "scheduled_tasks",
        "Geplante Tasks (Windows vs. eigene)",
        "Inventar & Tiefeninfos",
        176,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_system_profile() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $queryError = ""
        $result = $null

        try {
          $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
          $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop

          $productType = [int]$os.ProductType
          $isServer = ($productType -ne 1)

          $systemType = if ($isServer) { "Server" } else { "Client" }

          $productTypeText = switch ($productType) {
            1 { "Workstation" }
            2 { "Domain Controller" }
            3 { "Server" }
            default { "Unbekannt" }
          }

          $domainRole = [int]$cs.DomainRole
          $domainRoleText = switch ($domainRole) {
            0 { "Standalone Workstation" }
            1 { "Member Workstation" }
            2 { "Standalone Server" }
            3 { "Member Server" }
            4 { "Backup Domain Controller" }
            5 { "Primary Domain Controller" }
            default { "Unbekannt" }
          }

          $computerName = $env:COMPUTERNAME
          $fqdn = $computerName

          try {
            $ipProps = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
            if ($ipProps.HostName -and $ipProps.DomainName) {
              $fqdn = "$($ipProps.HostName).$($ipProps.DomainName)"
            } elseif ($cs.DNSHostName -and $cs.Domain -and $cs.PartOfDomain) {
              $fqdn = "$($cs.DNSHostName).$($cs.Domain)"
            } elseif ($cs.DNSHostName) {
              $fqdn = [string]$cs.DNSHostName
            }
          } catch {}

          $localDeviceId = ""
          try {
            $localDeviceId = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Cryptography" -Name "MachineGuid" -ErrorAction Stop).MachineGuid
          } catch {}

          $windowsProductId = ""
          try {
            $windowsProductId = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -Name "ProductId" -ErrorAction Stop).ProductId
          } catch {}

          [PSCustomObject]@{
            QuerySuccess      = $true
            QueryError        = ""
            ComputerName      = $computerName
            FQDN              = $fqdn
            SystemType        = $systemType
            IsServer          = $isServer
            ProductType       = $productType
            ProductTypeText   = $productTypeText
            DomainRole        = $domainRole
            DomainRoleText    = $domainRoleText
            Manufacturer      = $cs.Manufacturer
            Model             = $cs.Model
            LocalDeviceId     = $localDeviceId
            WindowsProductId  = $windowsProductId
          } | ConvertTo-Json -Compress
        } catch {
          [PSCustomObject]@{
            QuerySuccess      = $false
            QueryError        = $_.Exception.Message
            ComputerName      = $env:COMPUTERNAME
            FQDN              = $env:COMPUTERNAME
            SystemType        = "Unbekannt"
            IsServer          = $false
            ProductType       = $null
            ProductTypeText   = "Unbekannt"
            DomainRole        = $null
            DomainRoleText    = "Unbekannt"
            Manufacturer      = ""
            Model             = ""
            LocalDeviceId     = ""
            WindowsProductId  = ""
          } | ConvertTo-Json -Compress
        }
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Systemprofil-Modul lieferte kein Dictionary zurück.")

    query_success = bool(data.get("QuerySuccess", False))
    query_error = str(data.get("QueryError", "") or "").strip()
    system_type = str(data.get("SystemType", "") or "").strip()
    domain_role_text = str(data.get("DomainRoleText", "") or "").strip()
    fqdn = str(data.get("FQDN", "") or "").strip()
    manufacturer = str(data.get("Manufacturer", "") or "").strip()
    model = str(data.get("Model", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if not query_success:
        status = "warning"
        summary = "Systemprofil konnte nicht vollständig ermittelt werden"
        issues.append(f"Systemtyp/Rolle konnte nicht ermittelt werden: {query_error or 'Unbekannter Fehler'}")
    else:
        summary = f"{system_type} | {domain_role_text}"
        if fqdn:
            summary += f" | {fqdn}"
        if manufacturer or model:
            summary += f" | {manufacturer} {model}".strip()

    return make_result(
        "system_profile",
        "Systemprofil / Gerätetyp",
        "Übersicht",
        22,
        "kv",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_server_roles_features() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Has-Cmd($name) {
          return [bool](Get-Command $name -ErrorAction SilentlyContinue)
        }

        $queryError = ""
        $isServer = $false
        $systemType = "Client"
        $productTypeText = "Workstation"
        $roles = @()
        $rolesFound = @()

        try {
          $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
          $productType = [int]$os.ProductType
          $isServer = ($productType -ne 1)

          $productTypeText = switch ($productType) {
            1 { "Workstation" }
            2 { "Domain Controller" }
            3 { "Server" }
            default { "Unbekannt" }
          }

          $systemType = if ($isServer) { "Server" } else { "Client" }

          if ($isServer) {
            $featureMap = @(
              @{ Name = "AD-Domain-Services"; Display = "Active Directory Domain Services"; Group = "Identität" }
              @{ Name = "DNS"; Display = "DNS Server"; Group = "Netzwerk" }
              @{ Name = "DHCP"; Display = "DHCP Server"; Group = "Netzwerk" }
              @{ Name = "FS-FileServer"; Display = "File Server"; Group = "Dateidienste" }
              @{ Name = "FS-DFS-Namespace"; Display = "DFS Namespace"; Group = "Dateidienste" }
              @{ Name = "FS-DFS-Replication"; Display = "DFS Replication"; Group = "Dateidienste" }
              @{ Name = "Web-Server"; Display = "IIS Web Server"; Group = "Web" }
              @{ Name = "Web-WebServer"; Display = "IIS Web Server Core"; Group = "Web" }
              @{ Name = "Hyper-V"; Display = "Hyper-V"; Group = "Virtualisierung" }
              @{ Name = "Print-Server"; Display = "Print Server"; Group = "Druck" }
              @{ Name = "RDS-RD-Server"; Display = "Remote Desktop Session Host"; Group = "Remote Desktop Services" }
              @{ Name = "RDS-Licensing"; Display = "Remote Desktop Licensing"; Group = "Remote Desktop Services" }
              @{ Name = "Failover-Clustering"; Display = "Failover Clustering"; Group = "Hochverfügbarkeit" }
              @{ Name = "Windows-Server-Backup"; Display = "Windows Server Backup"; Group = "Backup" }
              @{ Name = "NPAS"; Display = "Network Policy and Access Services"; Group = "Netzwerk" }
            )

            if (Has-Cmd "Get-WindowsFeature") {
              $features = @{}
              foreach ($f in @(Get-WindowsFeature -ErrorAction Stop)) {
                $features[$f.Name] = $f
              }

              foreach ($entry in $featureMap) {
                if ($features.ContainsKey($entry.Name)) {
                  $feature = $features[$entry.Name]
                  if ($feature.Installed) {
                    $roles += [PSCustomObject]@{
                      Name        = $entry.Name
                      DisplayName = $entry.Display
                      Group       = $entry.Group
                      InstallState = "Installed"
                      Source      = "Get-WindowsFeature"
                    }
                    $rolesFound += $entry.Display
                  }
                }
              }
            }
            elseif (Has-Cmd "Get-WindowsOptionalFeature") {
              foreach ($entry in $featureMap) {
                try {
                  $feature = Get-WindowsOptionalFeature -Online -FeatureName $entry.Name -ErrorAction Stop
                  if ($feature.State -eq "Enabled") {
                    $roles += [PSCustomObject]@{
                      Name        = $entry.Name
                      DisplayName = $entry.Display
                      Group       = $entry.Group
                      InstallState = "Enabled"
                      Source      = "Get-WindowsOptionalFeature"
                    }
                    $rolesFound += $entry.Display
                  }
                } catch {}
              }
            }
            else {
              $queryError = "Weder Get-WindowsFeature noch Get-WindowsOptionalFeature verfügbar."
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        [PSCustomObject]@{
          QueryError          = $queryError
          SystemType          = $systemType
          IsServer            = $isServer
          ProductTypeText     = $productTypeText
          InstalledRoleCount  = @($roles).Count
          InstalledRoles      = @($roles | Sort-Object Group, DisplayName)
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Serverrollen-Modul lieferte kein Dictionary zurück.")

    is_server = bool(data.get("IsServer", False))
    system_type = str(data.get("SystemType", "") or "").strip()
    product_type_text = str(data.get("ProductTypeText", "") or "").strip()
    installed_role_count = int(data.get("InstalledRoleCount", 0) or 0)
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if not is_server:
        status = "info"
        summary = f"{system_type}-System erkannt – Serverrollen auf diesem Gerät nicht relevant"
    elif query_error and installed_role_count == 0:
        status = "warning"
        summary = "Serverrollen/Features konnten nicht ermittelt werden"
        issues.append(f"Rollen-/Feature-Abfrage fehlgeschlagen: {query_error}")
    elif installed_role_count == 0:
        status = "info"
        summary = f"{product_type_text} erkannt | keine der überwachten Kernrollen gefunden"
    else:
        status = "ok"
        summary = f"{product_type_text} | {installed_role_count} relevante Rolle(n)/Feature(s) erkannt"

    return make_result(
        "server_roles_features",
        "Rollen / Features auf Servern",
        "Inventar & Tiefeninfos",
        165,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_hardware_drivers() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Normalize-DateSafe($value) {
          try {
            if ($null -eq $value) { return "" }
            return ([datetime]$value).ToString("yyyy-MM-dd")
          } catch {
            return ""
          }
        }

        $devices = @()
        $queryError = ""

        try {
          $pnpMap = @{}
          foreach ($dev in @(Get-CimInstance Win32_PnPEntity -ErrorAction Stop)) {
            if ($dev.PNPDeviceID) {
              $pnpMap[[string]$dev.PNPDeviceID] = $dev
            }
          }

          foreach ($drv in @(Get-CimInstance Win32_PnPSignedDriver -ErrorAction Stop)) {
            $pnpId = [string]$drv.DeviceID
            $dev = $null
            if ($pnpId -and $pnpMap.ContainsKey($pnpId)) {
              $dev = $pnpMap[$pnpId]
            }

            $deviceClass = [string]$drv.DeviceClass
            $deviceName = if ($drv.DeviceName) { [string]$drv.DeviceName } else { [string]$drv.FriendlyName }
            $provider = [string]$drv.DriverProviderName
            $errorCode = if ($dev -and $null -ne $dev.ConfigManagerErrorCode) { [int]$dev.ConfigManagerErrorCode } else { 0 }
            $status = if ($dev -and $dev.Status) { [string]$dev.Status } else { "" }

            $isImportantClass = $deviceClass -in @(
              "NET",
              "SCSIAdapter",
              "HDC",
              "System",
              "Display",
              "MEDIA",
              "USB"
            )

            $isGeneric = $false
            if ($provider) {
              $provLower = $provider.ToLowerInvariant()
              if ($provLower -match "microsoft" -or $provLower -match "generic" -or $provLower -match "standard") {
                $isGeneric = $true
              }
            }

            if ($errorCode -ne 0 -or $isImportantClass -or $isGeneric) {
              $issueType = ""
              if ($errorCode -ne 0) {
                $issueType = "Gerätefehler"
              } elseif ($isGeneric -and $isImportantClass) {
                $issueType = "Wichtige Klasse mit generischem Treiber"
              } elseif ($isGeneric) {
                $issueType = "Generischer Treiber"
              } else {
                $issueType = "Wichtige Geräteklasse"
              }

              $devices += [PSCustomObject]@{
                DeviceName              = $deviceName
                DeviceClass             = $deviceClass
                Manufacturer            = [string]$drv.Manufacturer
                DriverProviderName      = $provider
                DriverVersion           = [string]$drv.DriverVersion
                DriverDate              = Normalize-DateSafe $drv.DriverDate
                Status                  = $status
                ConfigManagerErrorCode  = $errorCode
                IssueType               = $issueType
                PNPDeviceID             = $pnpId
              }
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        $problemCount = @($devices | Where-Object { $_.ConfigManagerErrorCode -ne 0 }).Count
        $genericCount = @($devices | Where-Object { $_.IssueType -match "Generischer Treiber" }).Count
        $criticalClassProblemCount = @(
          $devices | Where-Object {
            $_.ConfigManagerErrorCode -ne 0 -and $_.DeviceClass -in @("NET", "SCSIAdapter", "HDC", "System")
          }
        ).Count

        [PSCustomObject]@{
          QueryError                 = $queryError
          Device_Count               = @($devices).Count
          Problem_Device_Count       = $problemCount
          Generic_Driver_Count       = $genericCount
          Critical_Class_Problem_Count = $criticalClassProblemCount
          Devices                    = @($devices | Sort-Object `
            @{Expression={ if ($_.ConfigManagerErrorCode -ne 0) { 0 } else { 1 } }},
            DeviceClass,
            DeviceName | Select-Object -First 80)
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Hardware/Treiber-Modul lieferte kein Dictionary zurück.")

    device_count = int(data.get("Device_Count", 0) or 0)
    problem_count = int(data.get("Problem_Device_Count", 0) or 0)
    generic_count = int(data.get("Generic_Driver_Count", 0) or 0)
    critical_class_problem_count = int(data.get("Critical_Class_Problem_Count", 0) or 0)
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if device_count == 0 and query_error:
        status = "warning"
        summary = "Hardware-/Treiberdaten konnten nicht gelesen werden"
        issues.append(f"Treiberabfrage fehlgeschlagen: {query_error}")
    elif critical_class_problem_count > 0:
        status = "critical"
        summary = f"Gerätefehler: {problem_count} | kritisch relevante Klassen: {critical_class_problem_count}"
        issues.append(f"{critical_class_problem_count} Problemgerät(e) in Netzwerk/Storage/System erkannt.")
    elif problem_count > 0:
        status = "warning"
        summary = f"Gerätefehler: {problem_count} | generische Treiber: {generic_count}"
        issues.append(f"{problem_count} Gerät(e) mit ConfigManager-Fehlercode erkannt.")
    elif generic_count > 0:
        status = "info"
        summary = f"Keine Gerätefehler | generische Treiberhinweise: {generic_count}"
        issues.append(f"{generic_count} Gerät(e) mit generischem/Standard-Treiber erfasst.")
    else:
        summary = "Keine auffälligen Hardware-/Treiberprobleme erkannt"

    return make_result(
        "hardware_drivers",
        "Hardware / Treiber-Basischeck",
        "Inventar & Tiefeninfos",
        64,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_network_deep() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Safe-Join($value) {
          if ($null -eq $value) { return "" }
          if ($value -is [array]) { return ($value -join ", ") }
          return [string]$value
        }

        $rows = @()
        $queryError = ""
        $multiGateway = $false
        $apipaCount = 0
        $missingDnsCount = 0
        $disconnectedCount = 0

        try {
          if (Get-Command Get-NetAdapter -ErrorAction SilentlyContinue) {
            $configs = @{}
            foreach ($cfg in @(Get-NetIPConfiguration -ErrorAction SilentlyContinue)) {
              $configs[$cfg.InterfaceIndex] = $cfg
            }

            $upGateways = @()

            foreach ($nic in @(Get-NetAdapter -IncludeHidden -ErrorAction Stop)) {
              $cfg = $null
              if ($configs.ContainsKey($nic.ifIndex)) {
                $cfg = $configs[$nic.ifIndex]
              }

              $ipv4 = ""
              $dns = ""
              $gateway = ""
              $apipa = $false

              if ($cfg) {
                try { $ipv4 = (@($cfg.IPv4Address | ForEach-Object { $_.IPAddress }) -join ", ") } catch {}
                try { $dns = (@($cfg.DNSServer.ServerAddresses) -join ", ") } catch {}
                try { $gateway = (@($cfg.IPv4DefaultGateway | ForEach-Object { $_.NextHop }) -join ", ") } catch {}
              }

              if ($ipv4 -match '169\.254\.') {
                $apipa = $true
                $apipaCount++
              }

              if ($nic.Status -ne "Up" -and -not $nic.Virtual) {
                $disconnectedCount++
              }

              if ($nic.Status -eq "Up" -and $gateway) {
                $upGateways += ($gateway -split ',\s*')
              }

              if ($nic.Status -eq "Up" -and -not $dns) {
                $missingDnsCount++
              }

              $rows += [PSCustomObject]@{
                Name              = [string]$nic.Name
                InterfaceAlias    = [string]$nic.InterfaceAlias
                InterfaceDescription = [string]$nic.InterfaceDescription
                Status            = [string]$nic.Status
                LinkSpeed         = [string]$nic.LinkSpeed
                MacAddress        = [string]$nic.MacAddress
                VirtualAdapter    = [bool]$nic.Virtual
                HardwareInterface = [bool]$nic.HardwareInterface
                IPv4              = $ipv4
                DefaultGateway    = $gateway
                DnsServers        = $dns
                ApipaDetected     = $apipa
              }
            }

            $uniqueGateways = @($upGateways | Where-Object { $_ } | Sort-Object -Unique)
            if ($uniqueGateways.Count -gt 1) {
              $multiGateway = $true
            }
          } else {
            foreach ($a in @(Get-WmiObject Win32_NetworkAdapterConfiguration -ErrorAction Stop | Where-Object { $_.IPEnabled })) {
              $ipv4 = Safe-Join ($a.IPAddress | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' })
              $dns = Safe-Join $a.DNSServerSearchOrder
              $gateway = Safe-Join $a.DefaultIPGateway
              $apipa = ($ipv4 -match '169\.254\.')
              if ($apipa) { $apipaCount++ }
              if (-not $dns) { $missingDnsCount++ }

              $rows += [PSCustomObject]@{
                Name              = [string]$a.Description
                InterfaceAlias    = ""
                InterfaceDescription = [string]$a.Description
                Status            = "Unbekannt"
                LinkSpeed         = ""
                MacAddress        = [string]$a.MACAddress
                VirtualAdapter    = $null
                HardwareInterface = $null
                IPv4              = $ipv4
                DefaultGateway    = $gateway
                DnsServers        = $dns
                ApipaDetected     = $apipa
              }
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        [PSCustomObject]@{
          QueryError            = $queryError
          Adapter_Count         = @($rows).Count
          Multi_Gateway_Detected = $multiGateway
          Apipa_Count           = $apipaCount
          Missing_Dns_Count     = $missingDnsCount
          Disconnected_Count    = $disconnectedCount
          Adapters              = @($rows | Sort-Object `
            @{Expression={ if ($_.Status -eq "Up") { 0 } else { 1 } }},
            Name)
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Netzwerk-Vertiefung lieferte kein Dictionary zurück.")

    adapter_count = int(data.get("Adapter_Count", 0) or 0)
    apipa_count = int(data.get("Apipa_Count", 0) or 0)
    missing_dns_count = int(data.get("Missing_Dns_Count", 0) or 0)
    disconnected_count = int(data.get("Disconnected_Count", 0) or 0)
    multi_gateway = bool(data.get("Multi_Gateway_Detected", False))
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if adapter_count == 0 and query_error:
        status = "warning"
        summary = "Vertiefte Netzwerkdaten konnten nicht gelesen werden"
        issues.append(f"Erweiterte Netzwerkabfrage fehlgeschlagen: {query_error}")
    else:
        summary = f"{adapter_count} Adapter | APIPA: {apipa_count} | fehlendes DNS: {missing_dns_count}"

        if multi_gateway:
            status = "warning"
            issues.append("Mehrere unterschiedliche Default Gateways auf aktiven Adaptern erkannt.")
        if apipa_count > 0:
            status = "warning" if status != "critical" else status
            issues.append(f"{apipa_count} Adapter mit APIPA-Adresse erkannt.")
        if missing_dns_count > 0 and status == "ok":
            status = "info"
            issues.append(f"{missing_dns_count} aktive/r Adapter ohne DNS-Server-Eintrag.")
        if disconnected_count > 0 and status == "ok":
            status = "info"
            issues.append(f"{disconnected_count} nicht-virtuelle/r Adapter derzeit nicht aktiv.")

    return make_result(
        "network_deep",
        "Netzwerk vertiefen",
        "Netzwerk",
        74,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_dns_dhcp_basis() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Has-Cmd($name) {
          return [bool](Get-Command $name -ErrorAction SilentlyContinue)
        }

        $queryError = ""
        $isServer = $false
        $serverRole = ""
        $dnsInstalled = $false
        $dhcpInstalled = $false
        $dnsServiceStatus = "Nicht vorhanden"
        $dhcpServiceStatus = "Nicht vorhanden"
        $dnsZoneCount = $null
        $dhcpScopeCount = $null
        $dhcpAuthorized = $null

        try {
          $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
          $isServer = ([int]$os.ProductType -ne 1)
          $serverRole = if ($isServer) { "Server" } else { "Client" }

          if ($isServer) {
            $hasDnsZoneCmd = Has-Cmd "Get-DnsServerZone"
            $hasDhcpScopeCmd = Has-Cmd "Get-DhcpServerv4Scope"
            $hasDhcpInDcCmd = Has-Cmd "Get-DhcpServerInDC"

            $dnsSvc = Get-Service DNS -ErrorAction SilentlyContinue
            if ($dnsSvc) {
              $dnsInstalled = $true
              $dnsServiceStatus = $dnsSvc.Status.ToString()
            }

            $dhcpSvc = Get-Service DHCPServer -ErrorAction SilentlyContinue
            if ($dhcpSvc) {
              $dhcpInstalled = $true
              $dhcpServiceStatus = $dhcpSvc.Status.ToString()
            }

            if ($dnsInstalled -and $hasDnsZoneCmd) {
              try {
                $dnsZoneCount = @(Get-DnsServerZone -ErrorAction Stop).Count
              } catch {}
            }

            if ($dhcpInstalled -and $hasDhcpScopeCmd) {
              try {
                $dhcpScopeCount = @(Get-DhcpServerv4Scope -ErrorAction Stop).Count
              } catch {}
            }

            if ($dhcpInstalled -and $hasDhcpInDcCmd) {
              try {
                $auth = @(Get-DhcpServerInDC -ErrorAction Stop)
                if ($auth) {
                  $hostname = $env:COMPUTERNAME.ToLowerInvariant()
                  $dhcpAuthorized = [bool](@($auth | Where-Object {
                    $_.DnsName.ToLowerInvariant().StartsWith($hostname)
                  }).Count -gt 0)
                }
              } catch {}
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        [PSCustomObject]@{
          QueryError         = $queryError
          IsServer           = $isServer
          ServerRole         = $serverRole
          DNS_Installed      = $dnsInstalled
          DNS_ServiceStatus  = $dnsServiceStatus
          DNS_ZoneCount      = $dnsZoneCount
          DHCP_Installed     = $dhcpInstalled
          DHCP_ServiceStatus = $dhcpServiceStatus
          DHCP_ScopeCount    = $dhcpScopeCount
          DHCP_Authorized    = $dhcpAuthorized
        } | ConvertTo-Json -Compress -Depth 4
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("DNS/DHCP-Modul lieferte kein Dictionary zurück.")

    is_server = bool(data.get("IsServer", False))
    dns_installed = bool(data.get("DNS_Installed", False))
    dhcp_installed = bool(data.get("DHCP_Installed", False))
    dns_service = str(data.get("DNS_ServiceStatus", "") or "").strip()
    dhcp_service = str(data.get("DHCP_ServiceStatus", "") or "").strip()
    dns_zone_count = data.get("DNS_ZoneCount")
    dhcp_scope_count = data.get("DHCP_ScopeCount")
    dhcp_authorized = data.get("DHCP_Authorized")
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if not is_server:
        status = "info"
        summary = "Client-System erkannt – DNS-/DHCP-Serverrollen hier nicht relevant"
    elif query_error and not dns_installed and not dhcp_installed:
        status = "warning"
        summary = "DNS-/DHCP-Basischeck konnte nicht vollständig ausgeführt werden"
        issues.append(f"DNS/DHCP-Abfrage fehlgeschlagen: {query_error}")
    elif not dns_installed and not dhcp_installed:
        status = "info"
        summary = "Keine DNS-/DHCP-Serverrolle erkannt"
    else:
        summary_parts = []

        if dns_installed:
            summary_parts.append(f"DNS: {dns_service}")
            if dns_service != "Running":
                status = "warning"
                issues.append(f"DNS-Dienst läuft nicht sauber: {dns_service}")
            if dns_zone_count is not None:
                summary_parts.append(f"Zonen: {dns_zone_count}")

        if dhcp_installed:
            summary_parts.append(f"DHCP: {dhcp_service}")
            if dhcp_service != "Running":
                status = "warning"
                issues.append(f"DHCP-Dienst läuft nicht sauber: {dhcp_service}")
            if dhcp_scope_count is not None:
                summary_parts.append(f"Scopes: {dhcp_scope_count}")
            if dhcp_authorized is False:
                status = "warning"
                issues.append("DHCP-Server wirkt nicht autorisiert.")
            elif dhcp_authorized is True:
                summary_parts.append("DHCP autorisiert")

        summary = " | ".join(summary_parts) if summary_parts else "DNS/DHCP erkannt"

    return make_result(
        "dns_dhcp_basis",
        "DNS-/DHCP-Basischeck",
        "Inventar & Tiefeninfos",
        166,
        "kv",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_ad_dc_basis() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $queryError = ""
        $isDc = $false
        $domainRoleText = "Unbekannt"
        $services = @()
        $shares = @()

        try {
          $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
          $domainRole = [int]$cs.DomainRole
          $isDc = ($domainRole -in 4, 5)

          $domainRoleText = switch ($domainRole) {
            0 { "Standalone Workstation" }
            1 { "Member Workstation" }
            2 { "Standalone Server" }
            3 { "Member Server" }
            4 { "Backup Domain Controller" }
            5 { "Primary Domain Controller" }
            default { "Unbekannt" }
          }

          if ($isDc) {
            $serviceNames = @("NTDS", "DFSR", "Netlogon", "Kdc", "ADWS", "DNS")
            foreach ($name in $serviceNames) {
              $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
              if ($svc) {
                $services += [PSCustomObject]@{
                  Name    = $svc.Name
                  Status  = $svc.Status.ToString()
                  Present = $true
                }
              } else {
                $services += [PSCustomObject]@{
                  Name    = $name
                  Status  = "Nicht vorhanden"
                  Present = $false
                }
              }
            }

            foreach ($share in @(Get-CimInstance Win32_Share -ErrorAction SilentlyContinue)) {
              if ($share.Name -in @("SYSVOL", "NETLOGON")) {
                $shares += [PSCustomObject]@{
                  ShareName = [string]$share.Name
                  Path      = [string]$share.Path
                }
              }
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        [PSCustomObject]@{
          QueryError      = $queryError
          IsDomainController = $isDc
          DomainRoleText  = $domainRoleText
          Dc_Service_Count = @($services).Count
          Dc_Share_Count  = @($shares).Count
          DcServices      = $services
          DcShares        = $shares
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("AD/DC-Modul lieferte kein Dictionary zurück.")

    is_dc = bool(data.get("IsDomainController", False))
    domain_role_text = str(data.get("DomainRoleText", "") or "").strip()
    dc_share_count = int(data.get("Dc_Share_Count", 0) or 0)
    services = ensure_list(data.get("DcServices", []))
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if not is_dc:
        status = "info"
        summary = f"{domain_role_text} – DC-Basischeck auf diesem System nicht relevant"
    elif query_error and not services:
        status = "warning"
        summary = "AD/DC-Basischeck konnte nicht vollständig ausgeführt werden"
        issues.append(f"DC-Abfrage fehlgeschlagen: {query_error}")
    else:
        not_running = [svc.get("Name", "") for svc in services if svc.get("Present") and svc.get("Status") != "Running"]
        missing = [svc.get("Name", "") for svc in services if not svc.get("Present")]

        if not_running:
            status = "warning"
            issues.append(f"DC-relevante Dienste nicht aktiv: {', '.join(not_running)}")
        if missing:
            status = "warning"
            issues.append(f"DC-relevante Dienste fehlen: {', '.join(missing)}")
        if dc_share_count < 2:
            status = "warning"
            issues.append("SYSVOL und/oder NETLOGON Share fehlen oder wurden nicht erkannt.")

        if status == "ok":
            summary = f"Domain Controller erkannt | Dienste geprüft | SYSVOL/NETLOGON vorhanden"
        else:
            summary = f"Domain Controller erkannt | Shares: {dc_share_count} | Dienste: {len(services)}"

    return make_result(
        "ad_dc_basis",
        "AD-Server / DC-Basischeck",
        "Inventar & Tiefeninfos",
        167,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_iis_webserver_basis() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Has-Cmd($name) {
          return [bool](Get-Command $name -ErrorAction SilentlyContinue)
        }

        $queryError = ""
        $isServer = $false
        $iisInstalled = $false
        $w3svcStatus = "Nicht vorhanden"
        $sites = @()
        $appPools = @()

        try {
          $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
          $isServer = ([int]$os.ProductType -ne 1)

          if ($isServer) {
            $hasWebsiteCmd = Has-Cmd "Get-Website"
            $hasWebAppPoolStateCmd = Has-Cmd "Get-WebAppPoolState"

            $svc = Get-Service W3SVC -ErrorAction SilentlyContinue
            if ($svc) {
              $iisInstalled = $true
              $w3svcStatus = $svc.Status.ToString()
            }

            if ($iisInstalled -and $hasWebsiteCmd) {
              try {
                foreach ($site in @(Get-Website -ErrorAction Stop)) {
                  $bindingInfo = ""
                  try {
                    $bindingInfo = (@($site.Bindings.Collection | ForEach-Object {
                      "{0}:{1}" -f $_.protocol, $_.bindingInformation
                    }) -join " | ")
                  } catch {}

                  $httpsCount = 0
                  try {
                    $httpsCount = @($site.Bindings.Collection | Where-Object { $_.protocol -eq "https" }).Count
                  } catch {}

                  $sites += [PSCustomObject]@{
                    Name              = [string]$site.Name
                    State             = [string]$site.State
                    PhysicalPath      = [string]$site.PhysicalPath
                    BindingInfo       = $bindingInfo
                    HttpsBindingCount = $httpsCount
                  }
                }
              } catch {}
            }

            if ($iisInstalled -and $hasWebAppPoolStateCmd) {
              try {
                Import-Module WebAdministration -ErrorAction SilentlyContinue | Out-Null

                foreach ($pool in @(Get-ChildItem IIS:\AppPools -ErrorAction SilentlyContinue)) {
                  $state = ""
                  try {
                    $state = (Get-WebAppPoolState -Name $pool.Name -ErrorAction Stop).Value
                  } catch {}

                  $appPools += [PSCustomObject]@{
                    Name  = [string]$pool.Name
                    State = [string]$state
                  }
                }
              } catch {}
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        [PSCustomObject]@{
          QueryError    = $queryError
          IsServer      = $isServer
          IIS_Installed = $iisInstalled
          W3SVC_Status  = $w3svcStatus
          Site_Count    = @($sites).Count
          AppPool_Count = @($appPools).Count
          Sites         = $sites
          AppPools      = $appPools
        } | ConvertTo-Json -Compress -Depth 6
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("IIS-Modul lieferte kein Dictionary zurück.")

    is_server = bool(data.get("IsServer", False))
    iis_installed = bool(data.get("IIS_Installed", False))
    w3svc_status = str(data.get("W3SVC_Status", "") or "").strip()
    sites = ensure_list(data.get("Sites", []))
    app_pools = ensure_list(data.get("AppPools", []))
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if not is_server:
        status = "info"
        summary = "Client-System erkannt – IIS-Basischeck hier nicht relevant"
    elif query_error and not iis_installed:
        status = "warning"
        summary = "IIS-Basischeck konnte nicht vollständig ausgeführt werden"
        issues.append(f"IIS-Abfrage fehlgeschlagen: {query_error}")
    elif not iis_installed:
        status = "info"
        summary = "Kein IIS-Webserver erkannt"
    else:
        stopped_sites = [x.get("Name", "") for x in sites if str(x.get("State", "")).lower() != "started"]
        stopped_pools = [x.get("Name", "") for x in app_pools if str(x.get("State", "")).lower() not in {"started", ""}]
        sites_without_https = [x.get("Name", "") for x in sites if int(x.get("HttpsBindingCount", 0) or 0) == 0]

        if w3svc_status != "Running":
            status = "warning"
            issues.append(f"W3SVC läuft nicht sauber: {w3svc_status}")
        if stopped_sites:
            status = "warning"
            issues.append(f"Gestoppte IIS-Sites: {', '.join(stopped_sites[:6])}")
        if stopped_pools:
            status = "warning"
            issues.append(f"Gestoppte AppPools: {', '.join(stopped_pools[:6])}")
        if sites_without_https and status == "ok":
            status = "info"
            issues.append(f"Sites ohne HTTPS-Binding: {', '.join(sites_without_https[:6])}")

        summary = f"IIS erkannt | Sites: {len(sites)} | AppPools: {len(app_pools)} | W3SVC: {w3svc_status}"

    return make_result(
        "iis_webserver_basis",
        "IIS-Webserver-Basischeck",
        "Inventar & Tiefeninfos",
        168,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def _history_extract_result(results: list[dict[str, Any]], module_id: str) -> dict[str, Any] | None:
    for result in results:
        if str(result.get("id", "")) == module_id:
            return result
    return None


def _history_software_set(result: dict[str, Any] | None) -> set[str]:
    if not result:
        return set()
    data = result.get("data", {})
    if not isinstance(data, dict):
        return set()
    rows = ensure_list(data.get("Software", []))
    values = set()
    for row in rows:
        name = str(row.get("DisplayName", "")).strip()
        version = str(row.get("DisplayVersion", "")).strip()
        if name:
            values.add(f"{name}|{version}")
    return values


def _history_port_set(result: dict[str, Any] | None) -> set[str]:
    if not result:
        return set()
    data = result.get("data", {})
    if not isinstance(data, dict):
        return set()
    rows = ensure_list(data.get("VisiblePorts", []))
    values = set()
    for row in rows:
        port = str(row.get("LocalPort", "")).strip()
        proc = str(row.get("ProcessName", "")).strip()
        if port:
            values.add(f"{port}|{proc}")
    return values


def _history_share_set(result: dict[str, Any] | None) -> set[str]:
    if not result:
        return set()
    data = result.get("data", {})
    if not isinstance(data, dict):
        return set()
    rows = ensure_list(data.get("Shares", []))
    values = set()
    for row in rows:
        name = str(row.get("ShareName", "")).strip()
        if name:
            values.add(name)
    return values


def build_history_result(current_results: list[dict[str, Any]]) -> dict[str, Any]:
    previous_report = None
    previous_results: list[dict[str, Any]] = []

    try:
        if JSON_OUTPUT.exists():
            previous_report = json.loads(JSON_OUTPUT.read_text(encoding="utf-8"))
            previous_results = previous_report.get("results", []) if isinstance(previous_report, dict) else []
    except Exception as exc:
        previous_report = {"_read_error": str(exc)}
        previous_results = []

    current_warning_modules = {
        f"{r.get('title', '')}|{r.get('status', '')}"
        for r in current_results
        if r.get("status") in {"warning", "critical"}
    }
    previous_warning_modules = {
        f"{r.get('title', '')}|{r.get('status', '')}"
        for r in previous_results
        if r.get("status") in {"warning", "critical"}
    }

    new_warning_modules = sorted(current_warning_modules - previous_warning_modules)
    resolved_warning_modules = sorted(previous_warning_modules - current_warning_modules)

    current_software = _history_software_set(_history_extract_result(current_results, "installed_software"))
    previous_software = _history_software_set(_history_extract_result(previous_results, "installed_software"))

    current_ports = _history_port_set(_history_extract_result(current_results, "ports"))
    previous_ports = _history_port_set(_history_extract_result(previous_results, "ports"))

    current_shares = _history_share_set(_history_extract_result(current_results, "shares"))
    previous_shares = _history_share_set(_history_extract_result(previous_results, "shares"))

    new_software = sorted(current_software - previous_software)
    new_ports = sorted(current_ports - previous_ports)
    new_shares = sorted(current_shares - previous_shares)

    previous_generated_at = ""
    if isinstance(previous_report, dict):
        previous_generated_at = str(previous_report.get("generated_at", "")).strip()

    issues: list[str] = []
    status = "ok"

    if previous_report is None:
        status = "info"
        summary = "Kein vorheriger Report für Vergleich vorhanden"
        data = {
            "Previous_Report_Found": False,
            "Previous_Generated_At": "",
            "New_Warning_Modules": [],
            "Resolved_Warning_Modules": [],
            "New_Software": [],
            "New_Visible_Ports": [],
            "New_Shares": [],
        }
    elif isinstance(previous_report, dict) and previous_report.get("_read_error"):
        status = "warning"
        summary = "Vorheriger Report konnte nicht gelesen werden"
        issues.append(f"Lesefehler beim letzten JSON-Report: {previous_report.get('_read_error')}")
        data = {
            "Previous_Report_Found": True,
            "Previous_Generated_At": "",
            "New_Warning_Modules": [],
            "Resolved_Warning_Modules": [],
            "New_Software": [],
            "New_Visible_Ports": [],
            "New_Shares": [],
        }
    else:
        if new_warning_modules or new_ports or new_shares:
            status = "warning"
        elif new_software:
            status = "info"

        if new_warning_modules:
            issues.append(f"Neue Warnungen/Kritisch-Module: {len(new_warning_modules)}")
        if resolved_warning_modules:
            issues.append(f"Behobene Warnungen/Kritisch-Module: {len(resolved_warning_modules)}")
        if new_software:
            issues.append(f"Neue Softwareeinträge seit letztem Lauf: {len(new_software)}")
        if new_ports:
            issues.append(f"Neue relevante offene Ports seit letztem Lauf: {len(new_ports)}")
        if new_shares:
            issues.append(f"Neue Freigaben seit letztem Lauf: {len(new_shares)}")

        if not issues:
            summary = f"Vergleich zu {previous_generated_at or 'vorherigem Lauf'}: keine relevanten Änderungen"
        else:
            summary = f"Vergleich zu {previous_generated_at or 'vorherigem Lauf'} | Änderungen: {len(issues)}"

        data = {
            "Previous_Report_Found": True,
            "Previous_Generated_At": previous_generated_at,
            "New_Warning_Modules": new_warning_modules[:20],
            "Resolved_Warning_Modules": resolved_warning_modules[:20],
            "New_Software": new_software[:30],
            "New_Visible_Ports": new_ports[:30],
            "New_Shares": new_shares[:30],
        }

    return make_result(
        "history_compare",
        "Historie / Vergleich zum letzten Lauf",
        "Inventar & Tiefeninfos",
        190,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )
    

def collect_systeminfo_summary() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Get-SysteminfoValue($lines, $labels) {
          foreach ($line in $lines) {
            foreach ($label in $labels) {
              if ($line -match ("^\s*" + [regex]::Escape($label) + "\s*:\s*(.+)$")) {
                return $matches[1].Trim()
              }
            }
          }
          return ""
        }

        $queryError = ""

        try {
          $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
          $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
          $bios = Get-CimInstance Win32_BIOS -ErrorAction SilentlyContinue

          $hostname = [string]$env:COMPUTERNAME

          $biosVersion = ""
          if ($bios) {
            $biosParts = @()
            if ($bios.Manufacturer) { $biosParts += [string]$bios.Manufacturer }
            if ($bios.SMBIOSBIOSVersion) { $biosParts += [string]$bios.SMBIOSBIOSVersion }
            if ($bios.ReleaseDate) {
              try {
                $biosParts += ([System.Management.ManagementDateTimeConverter]::ToDateTime($bios.ReleaseDate)).ToString("dd.MM.yyyy")
              } catch {}
            }
            $biosVersion = $biosParts -join ", "
          }

          $logonServer = ""
          try {
            $logonServer = [string]$env:LOGONSERVER
          } catch {}

          $domainInfo = ""
          if ($cs.PartOfDomain) {
            $domainInfo = [string]$cs.Domain
          } else {
            $domainInfo = [string]$cs.Workgroup
          }

          $systeminfoInstallDate = ""
          $installDateFallback = ""
          $installDateSource = ""

          try {
            $sysLines = & systeminfo.exe 2>$null

            if ($sysLines) {
              $systeminfoInstallDate = Get-SysteminfoValue $sysLines @(
                "Original Install Date",
                "Ursprüngliches Installationsdatum",
                "Installationsdatum"
              )
            }
          } catch {}

          if (-not [string]::IsNullOrWhiteSpace($systeminfoInstallDate)) {
            $installDateSource = "systeminfo.exe"
          } else {
            try {
              if ($os.InstallDate) {
                $installDateFallback = ([System.Management.ManagementDateTimeConverter]::ToDateTime($os.InstallDate)).ToString("dd.MM.yyyy, HH:mm:ss")
                $installDateSource = "Win32_OperatingSystem.InstallDate"
              }
            } catch {}
          }

          [PSCustomObject]@{
            QuerySuccess                  = $true
            QueryError                    = ""
            HostName                      = $hostname
            BiosVersion                   = $biosVersion
            OriginalInstallDate_SystemInfo = $systeminfoInstallDate
            OriginalInstallDate_Fallback   = $installDateFallback
            OriginalInstallDate            = if ($systeminfoInstallDate) { $systeminfoInstallDate } else { $installDateFallback }
            InstallDateSource              = $installDateSource
            LogonServer                   = $logonServer
            DomainInfo                    = $domainInfo
          } | ConvertTo-Json -Compress
        } catch {
          [PSCustomObject]@{
            QuerySuccess                  = $false
            QueryError                    = $_.Exception.Message
            HostName                      = ""
            BiosVersion                   = ""
            OriginalInstallDate_SystemInfo = ""
            OriginalInstallDate_Fallback   = ""
            OriginalInstallDate            = ""
            InstallDateSource              = ""
            LogonServer                   = ""
            DomainInfo                    = ""
          } | ConvertTo-Json -Compress
        }
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Systeminfo-Modul lieferte kein Dictionary zurück.")

    query_success = bool(data.get("QuerySuccess", False))
    query_error = str(data.get("QueryError", "") or "").strip()
    hostname = str(data.get("HostName", "") or "").strip()
    domain_info = str(data.get("DomainInfo", "") or "").strip()
    install_date = str(data.get("OriginalInstallDate", "") or "").strip()
    install_source = str(data.get("InstallDateSource", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if not query_success:
        status = "warning"
        summary = "Systeminfo konnte nicht gelesen werden"
        issues.append(f"Systeminfo-Abfrage fehlgeschlagen: {query_error or 'Unbekannter Fehler'}")
    else:
        summary = hostname or "Systeminfo erfolgreich gelesen"
        if install_date:
            summary += f" | Installiert: {install_date}"
        if install_source:
            summary += f" | Quelle: {install_source}"
        if domain_info:
            summary += f" | {domain_info}"

        if not install_date:
            status = "info"
            issues.append("Installationsdatum konnte weder aus systeminfo.exe noch per Fallback eindeutig gelesen werden.")

    return make_result(
        "systeminfo_summary",
        "Systeminfo",
        "Übersicht",
        10,
        "kv",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )
    


def collect_external_ip() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $queryError = ""
        $ip = ""
        $serviceUsed = ""

        $services = @(
          @{ Name = "ipify"; Url = "https://api.ipify.org?format=json"; Mode = "json" },
          @{ Name = "ifconfig.me"; Url = "https://ifconfig.me/ip"; Mode = "text" },
          @{ Name = "icanhazip"; Url = "https://ipv4.icanhazip.com"; Mode = "text" }
        )

        foreach ($svc in $services) {
          try {
            if ($svc.Mode -eq "json") {
              $resp = Invoke-RestMethod -Uri $svc.Url -Method Get -TimeoutSec 8 -ErrorAction Stop
              $candidate = [string]$resp.ip
            } else {
              $resp = Invoke-WebRequest -Uri $svc.Url -Method Get -UseBasicParsing -TimeoutSec 8 -ErrorAction Stop
              $candidate = ([string]$resp.Content).Trim()
            }

            if ($candidate) {
              $ip = $candidate.Trim()
              $serviceUsed = $svc.Name
              break
            }
          } catch {
            $queryError = $_.Exception.Message
          }
        }

        [PSCustomObject]@{
          QuerySuccess = -not [string]::IsNullOrWhiteSpace($ip)
          QueryError   = $queryError
          ExternalIP   = $ip
          ServiceUsed  = $serviceUsed
        } | ConvertTo-Json -Compress
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Externe-IP-Modul lieferte kein Dictionary zurück.")

    query_success = bool(data.get("QuerySuccess", False))
    query_error = str(data.get("QueryError", "") or "").strip()
    external_ip = str(data.get("ExternalIP", "") or "").strip()
    service_used = str(data.get("ServiceUsed", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if not query_success:
        status = "info"
        summary = "Externe Internet-IP konnte nicht ermittelt werden"
        if query_error:
            issues.append(f"Externe Abfrage nicht erfolgreich: {query_error}")
    else:
        status = "info"
        summary = f"{external_ip}"
        if service_used:
            summary += f" | via {service_used}"

    return make_result(
        "external_ip",
        "Externe Internet-IP",
        "Netzwerk",
        76,
        "kv",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_gpresult_summary() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Run-GpresultScope($scope) {
          try {
            $output = & gpresult /r /scope $scope 2>&1 | Out-String
            $text = ($output | Out-String).Trim()

            if ([string]::IsNullOrWhiteSpace($text)) {
              return [PSCustomObject]@{
                Success = $false
                Error   = "Keine Ausgabe"
                Text    = ""
              }
            }

            return [PSCustomObject]@{
              Success = $true
              Error   = ""
              Text    = $text
            }
          } catch {
            return [PSCustomObject]@{
              Success = $false
              Error   = $_.Exception.Message
              Text    = ""
            }
          }
        }

        $computer = Run-GpresultScope "computer"
        $user = Run-GpresultScope "user"

        [PSCustomObject]@{
          ComputerScopeSuccess = $computer.Success
          ComputerScopeError   = $computer.Error
          ComputerScopeText    = $computer.Text
          UserScopeSuccess     = $user.Success
          UserScopeError       = $user.Error
          UserScopeText        = $user.Text
        } | ConvertTo-Json -Compress -Depth 4
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("gpresult-Modul lieferte kein Dictionary zurück.")

    computer_ok = bool(data.get("ComputerScopeSuccess", False))
    user_ok = bool(data.get("UserScopeSuccess", False))
    computer_err = str(data.get("ComputerScopeError", "") or "").strip()
    user_err = str(data.get("UserScopeError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if computer_ok and user_ok:
        status = "ok"
        summary = "gpresult für Computer- und Benutzerkontext gelesen"
    elif computer_ok or user_ok:
        status = "info"
        summary = "gpresult nur teilweise verfügbar"
        if not computer_ok and computer_err:
            issues.append(f"Computerkontext: {computer_err}")
        if not user_ok and user_err:
            issues.append(f"Benutzerkontext: {user_err}")
    else:
        status = "warning"
        summary = "gpresult /r konnte nicht gelesen werden"
        if computer_err:
            issues.append(f"Computerkontext: {computer_err}")
        if user_err:
            issues.append(f"Benutzerkontext: {user_err}")

    return make_result(
        "gpresult_summary",
        "gpresult /r",
        "Inventar & Tiefeninfos",
        177,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_printers() -> dict[str, Any]:
    data = powershell_json(
        r"""
        function Has-Cmd($name) {
          return [bool](Get-Command $name -ErrorAction SilentlyContinue)
        }

        $queryError = ""
        $rows = @()

        try {
          if (Has-Cmd "Get-Printer") {
            foreach ($p in @(Get-Printer -ErrorAction Stop)) {
              $printerStatus = ""
              try { $printerStatus = [string]$p.PrinterStatus } catch {}

              $rows += [PSCustomObject]@{
                Name         = [string]$p.Name
                DriverName   = [string]$p.DriverName
                PortName     = [string]$p.PortName
                Shared       = [bool]$p.Shared
                ShareName    = [string]$p.ShareName
                Default      = [bool]$p.Default
                WorkOffline  = [bool]$p.WorkOffline
                PrinterStatus = $printerStatus
              }
            }
          } else {
            foreach ($p in @(Get-CimInstance Win32_Printer -ErrorAction Stop)) {
              $rows += [PSCustomObject]@{
                Name          = [string]$p.Name
                DriverName    = [string]$p.DriverName
                PortName      = [string]$p.PortName
                Shared        = [bool]$p.Shared
                ShareName     = [string]$p.ShareName
                Default       = [bool]$p.Default
                WorkOffline   = [bool]$p.WorkOffline
                PrinterStatus = [string]$p.PrinterStatus
              }
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        $sharedCount = @($rows | Where-Object { $_.Shared }).Count
        $offlineCount = @($rows | Where-Object { $_.WorkOffline }).Count
        $defaultCount = @($rows | Where-Object { $_.Default }).Count

        [PSCustomObject]@{
          QueryError      = $queryError
          Printer_Count   = @($rows).Count
          Shared_Count    = $sharedCount
          Offline_Count   = $offlineCount
          Default_Count   = $defaultCount
          Printers        = @($rows | Sort-Object Name)
        } | ConvertTo-Json -Compress -Depth 5
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Drucker-Modul lieferte kein Dictionary zurück.")

    printer_count = int(data.get("Printer_Count", 0) or 0)
    shared_count = int(data.get("Shared_Count", 0) or 0)
    offline_count = int(data.get("Offline_Count", 0) or 0)
    default_count = int(data.get("Default_Count", 0) or 0)
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if printer_count == 0 and query_error:
        status = "warning"
        summary = "Installierte Drucker konnten nicht gelesen werden"
        issues.append(f"Druckerabfrage fehlgeschlagen: {query_error}")
    elif printer_count == 0:
        status = "info"
        summary = "Keine installierten Drucker erkannt"
    else:
        summary = f"{printer_count} Drucker | Standard: {default_count} | Freigegeben: {shared_count}"
        if offline_count > 0:
            status = "info"
            issues.append(f"{offline_count} Drucker aktuell offline/WorkOffline.")
        else:
            status = "ok"

    return make_result(
        "printers",
        "Installierte Drucker",
        "Inventar & Tiefeninfos",
        162,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )
    

def collect_user_profiles_dirs() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $queryError = ""
        $rows = @()

        try {
          $basePath = Join-Path $env:SystemDrive "Users"

          if (-not (Test-Path $basePath)) {
            throw "Pfad '$basePath' wurde nicht gefunden."
          }

          $defaultNames = @(
            "Default",
            "Default User",
            "Public",
            "All Users",
            "defaultuser0",
            "WDAGUtilityAccount"
          )

          foreach ($dir in @(Get-ChildItem -Path $basePath -Directory -Force -ErrorAction Stop)) {
            $name = [string]$dir.Name
            $fullPath = [string]$dir.FullName
            $isDefaultProfile = $defaultNames -contains $name
            $ntUserDatPath = Join-Path $fullPath "NTUSER.DAT"
            $ntUserDatExists = Test-Path $ntUserDatPath

            $issueType = ""
            if (-not $isDefaultProfile -and -not $ntUserDatExists) {
              $issueType = "Profil ohne NTUSER.DAT"
            }

            $rows += [PSCustomObject]@{
              ProfileName       = $name
              FullPath          = $fullPath
              IsDefaultProfile  = $isDefaultProfile
              NtUserDatExists   = $ntUserDatExists
              LastWriteTime     = $dir.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
              IssueType         = $issueType
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }

        $profileCount = @($rows).Count
        $customProfileCount = @($rows | Where-Object { -not $_.IsDefaultProfile }).Count
        $orphanLikeCount = @(
          $rows | Where-Object {
            -not $_.IsDefaultProfile -and -not $_.NtUserDatExists
          }
        ).Count

        [PSCustomObject]@{
          QueryError           = $queryError
          Profile_BasePath     = (Join-Path $env:SystemDrive "Users")
          Profile_Count        = $profileCount
          Custom_Profile_Count = $customProfileCount
          OrphanLike_Count     = $orphanLikeCount
          Profiles             = @($rows | Sort-Object `
            @{Expression={ if ($_.IsDefaultProfile) { 1 } else { 0 } }},
            ProfileName)
        } | ConvertTo-Json -Compress -Depth 5
        """
    )

    if not isinstance(data, dict):
        raise RuntimeError("Benutzerprofile-Modul lieferte kein Dictionary zurück.")

    profile_count = int(data.get("Profile_Count", 0) or 0)
    custom_profile_count = int(data.get("Custom_Profile_Count", 0) or 0)
    orphan_like_count = int(data.get("OrphanLike_Count", 0) or 0)
    query_error = str(data.get("QueryError", "") or "").strip()

    status = "ok"
    issues: list[str] = []

    if profile_count == 0 and query_error:
        status = "warning"
        summary = "Benutzerprofile unter C:\\Users konnten nicht gelesen werden"
        issues.append(f"Profilordner-Abfrage fehlgeschlagen: {query_error}")
    elif profile_count == 0:
        status = "info"
        summary = "Keine Profilordner unter C:\\Users gefunden"
    else:
        summary = f"{custom_profile_count} Benutzerprofil(e) | gesamt: {profile_count}"
        if orphan_like_count > 0:
            status = "info"
            issues.append(f"{orphan_like_count} Profilordner ohne NTUSER.DAT erkannt.")
        else:
            status = "ok"

    return make_result(
        "user_profiles_dirs",
        "Benutzerprofile unter C:\\Users",
        "Benutzer & Last",
        145,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
    )


def collect_identity_context() -> dict[str, Any]:
    data = powershell_json(
        r"""
        try {
          $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
          $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
          $groups = @()
          foreach ($g in @($identity.Groups)) {
            try {
              $groups += $g.Translate([System.Security.Principal.NTAccount]).Value
            } catch {
              $groups += $g.Value
            }
          }
          $privs = @()
          try {
            $tmp = & whoami /priv 2>$null
            foreach ($line in @($tmp | Select-Object -Skip 1)) {
              $clean = ($line -replace '^\s+', '')
              if ($clean -and $clean -match '^Se') {
                $parts = $clean -split '\s{2,}'
                if ($parts.Count -ge 3) {
                  $privs += [PSCustomObject]@{ Name = $parts[0]; Beschreibung = $parts[1]; Status = $parts[2] }
                }
              }
            }
          } catch {}
          [PSCustomObject]@{
            UserName = [string]$identity.Name
            AuthenticationType = [string]$identity.AuthenticationType
            IsSystem = [bool]$identity.IsSystem
            IsAuthenticated = [bool]$identity.IsAuthenticated
            IsAdmin = [bool]($principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator))
            GroupCount = @($groups).Count
            EnabledPrivilegeCount = @($privs | Where-Object { $_.Status -match 'Enabled|Aktiviert' }).Count
            Groups = @($groups | Sort-Object | Select-Object -First 40)
            Privileges = @($privs | Select-Object -First 25)
          } | ConvertTo-Json -Compress -Depth 6
        } catch {
          throw $_
        }
        """
    )
    if not isinstance(data, dict):
        raise RuntimeError("Identitätskontext lieferte kein Dictionary zurück.")
    username = str(data.get("UserName", "") or "").strip()
    is_admin = bool(data.get("IsAdmin", False))
    group_count = int(data.get("GroupCount", 0) or 0)
    priv_count = int(data.get("EnabledPrivilegeCount", 0) or 0)
    status = "info"
    summary = f"{username or 'Benutzer unbekannt'} | Admin: {'Ja' if is_admin else 'Nein'} | Gruppen: {group_count} | aktive Privilegien: {priv_count}"
    return make_result(
        "identity_context",
        "Identität / Rechtekontext",
        "Sicherheit",
        172,
        "sections",
        data,
        status=status,
        summary=summary,
        description="Aktueller Benutzer, Gruppen und wirksame Rechte dieses Prozesses.",
    )


def collect_process_services_map() -> dict[str, Any]:
    raw = powershell_json(
        r"""
        $rows = [System.Collections.Generic.List[object]]::new()
        $queryError = ""

        function Add-ServiceRows($services) {
          $processMap = @{}
          foreach ($svc in @($services)) {
            $pidValue = $svc.ProcessId
            if ($null -eq $pidValue) { $pidValue = $svc.ProcessID }
            if ($null -eq $pidValue) { continue }
            $procPid = 0
            if (-not [int]::TryParse(([string]$pidValue), [ref]$procPid) -or $procPid -le 0) { continue }
            if (-not $processMap.ContainsKey($procPid)) {
              $processMap[$procPid] = [System.Collections.Generic.List[string]]::new()
            }
            $svcName = if ($svc.DisplayName) { [string]$svc.DisplayName } elseif ($svc.Name) { [string]$svc.Name } else { 'Unbekannter Dienst' }
            [void]$processMap[$procPid].Add($svcName)
          }

          foreach ($procPid in @($processMap.Keys | Sort-Object)) {
            $proc = Get-Process -Id $procPid -ErrorAction SilentlyContinue
            $procName = if ($proc) { [string]$proc.ProcessName } else { 'PID ' + $procPid }
            $sessionId = if ($proc -and $null -ne $proc.SessionId) { [int]$proc.SessionId } else { $null }
            [void]$rows.Add([PSCustomObject]@{
              ProcessName   = $procName
              OwningProcess = [int]$procPid
              Services      = (@($processMap[$procPid] | Sort-Object -Unique) -join ', ')
              SessionId     = $sessionId
            })
          }
        }

        try {
          $services = @(Get-CimInstance Win32_Service -ErrorAction Stop)
          Add-ServiceRows $services
        } catch {
          $queryError = $_.Exception.Message
          try {
            $services = @(Get-WmiObject Win32_Service -ErrorAction Stop)
            Add-ServiceRows $services
          } catch {
            if ($queryError) {
              $queryError += ' | WMI-Fallback: ' + $_.Exception.Message
            } else {
              $queryError = $_.Exception.Message
            }
          }
        }

        [PSCustomObject]@{
          QueryError = $queryError
          Rows       = @($rows | Sort-Object ProcessName, OwningProcess | Select-Object -First 300)
        } | ConvertTo-Json -Compress -Depth 6
        """
    )
    if not isinstance(raw, dict):
        raise RuntimeError("Prozess/Dienst-Modul lieferte kein Dictionary zurück.")

    data = ensure_list(raw.get("Rows", []))
    query_error = str(raw.get("QueryError", "") or "").strip()
    issues: list[str] = []

    if query_error:
        issues.append(f"Abfragehinweis: {query_error}")

    if data:
        status = "info"
        summary = f"{len(data)} Prozess(e) hosten Windows-Dienste"
    else:
        status = "warning" if query_error else "info"
        summary = "Keine Prozesse mit zugeordneten Windows-Diensten gefunden"
        if not query_error:
            issues.append("Es wurden keine Service-Hosts aus Win32_Service ermittelt.")

    return make_result(
        "process_services_map",
        "Prozesse mit Diensten",
        "Inventar & Tiefeninfos",
        211,
        "table",
        data,
        status=status,
        summary=summary,
        issues=issues,
        description="Zuordnung von Prozessen zu den darin laufenden Windows-Diensten.",
    )


def collect_kerberos_tickets() -> dict[str, Any]:
    data = powershell_json(
        r"""
        $tickets = @()
        $queryError = ""
        try {
          $raw = & klist 2>&1
          $text = ($raw | Out-String)
          if ($LASTEXITCODE -ne 0 -or $text -match 'No credentials available|Es sind keine Anmeldeinformationen') {
            $queryError = ($text.Trim())
          } else {
            $blocks = ($text -split "`r?`n`r?`n")
            foreach ($block in $blocks) {
              $server = [regex]::Match($block, 'Server:\s*(.+)').Groups[1].Value.Trim()
              if (-not $server) { continue }
              $client = [regex]::Match($block, 'Client:\s*(.+)').Groups[1].Value.Trim()
              $start = [regex]::Match($block, 'Start Time:\s*(.+)').Groups[1].Value.Trim()
              $end = [regex]::Match($block, 'End Time:\s*(.+)').Groups[1].Value.Trim()
              $renew = [regex]::Match($block, 'Renew Time:\s*(.+)').Groups[1].Value.Trim()
              $etype = [regex]::Match($block, 'KerbTicket Encryption Type:\s*(.+)').Groups[1].Value.Trim()
              $flags = [regex]::Match($block, 'Ticket Flags\s+0x[0-9a-fA-F]+\s*->\s*(.+)').Groups[1].Value.Trim()
              $tickets += [PSCustomObject]@{ ServerName=$server; Client=$client; StartTime=$start; EndTime=$end; RenewTime=$renew; EncryptionType=$etype; Flags=$flags }
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }
        [PSCustomObject]@{ QueryError=$queryError; Ticket_Count=@($tickets).Count; Tickets=@($tickets | Select-Object -First 40) } | ConvertTo-Json -Compress -Depth 6
        """
    )
    if not isinstance(data, dict):
        raise RuntimeError("Kerberos-Modul lieferte kein Dictionary zurück.")
    ticket_count = int(data.get("Ticket_Count", 0) or 0)
    query_error = str(data.get("QueryError", "") or "").strip()
    issues: list[str] = []
    running_as_admin = is_admin()

    if ticket_count == 0:
        status = "ok"
        if running_as_admin:
            summary = "Keine Kerberos-Tickets im aktuellen Administratorkontext sichtbar"
            issues.append("Hinweis: Die Abfrage läuft mit Administratorrechten. Kerberos-Tickets des interaktiven Benutzers werden in diesem Kontext oft nicht angezeigt.")
        else:
            summary = report_tr("kerberos_none")
        lowered_error = query_error.lower()
        if query_error and "no credentials available" not in lowered_error and "keine anmeldeinformationen" not in lowered_error:
            issues.append(query_error)
    else:
        status = "ok"
        summary = report_tr("kerberos_cache_fmt", count=ticket_count)
        if running_as_admin:
            issues.append("Ausgeführt mit Administratorrechten. Sichtbare Tickets gehören zum aktuellen Kontext.")
    return make_result(
        "kerberos_tickets",
        "Kerberos-Tickets",
        "Sicherheit",
        173,
        "sections",
        data,
        status=status,
        summary=summary,
        issues=issues,
        description=report_tr("kerberos_description"),
    )


def collect_vss_writers() -> dict[str, Any]:
    raw = powershell_json(
        r"""
        $writers = @()
        $queryError = ""
        try {
          $raw = & vssadmin list writers 2>&1
          $text = ($raw | Out-String)
          if ($LASTEXITCODE -ne 0) {
            $queryError = $text.Trim()
          } else {
            $normalized = ($text -replace "`r", "")
            $blocks = $normalized -split "`n\s*`n"
            foreach ($block in $blocks) {
              $trimmed = $block.Trim()
              if (-not $trimmed) { continue }
              if ($trimmed -notmatch '(?im)(writer|schattenkopie)') { continue }

              $name = ''
              $state = ''
              $lastError = ''
              $id = ''
              $instance = ''

              foreach ($line in ($trimmed -split "`n")) {
                $current = $line.Trim()
                if (-not $current) { continue }
                if (-not $name -and $current -match "(?i)(writer\s*name|writername|schattenkopie-?writer(?:name)?|verfassername)\s*:\s*(.+)$") {
                  $name = $matches[2].Trim(" '")
                  continue
                }
                if (-not $name -and $current -match "(?i)^name\s*:\s*(.+)$") {
                  $name = $matches[1].Trim(" '")
                  continue
                }
                if (-not $state -and $current -match "(?i)state\s*:\s*(?:\[[^\]]+\]\s*)?(.+)$") {
                  $state = $matches[1].Trim()
                  continue
                }
                if (-not $state -and $current -match "(?i)status\s*:\s*(?:\[[^\]]+\]\s*)?(.+)$") {
                  $state = $matches[1].Trim()
                  continue
                }
                if (-not $lastError -and $current -match "(?i)(last\s*error|letzter\s*fehler)\s*:\s*(.+)$") {
                  $lastError = $matches[2].Trim()
                  continue
                }
                if (-not $id -and $current -match "(?i)(writer\s*id|writer-id)\s*:\s*(.+)$") {
                  $id = $matches[2].Trim()
                  continue
                }
                if (-not $instance -and $current -match "(?i)(writer\s*instance\s*id|instanz-id|writer-instanz-id)\s*:\s*(.+)$") {
                  $instance = $matches[2].Trim()
                  continue
                }
              }

              if ($name -or $state -or $lastError -or $id -or $instance) {
                $writers += [PSCustomObject]@{ Name=$name; State=$state; LastError=$lastError; WriterId=$id; InstanceId=$instance }
              }
            }
          }
        } catch {
          $queryError = $_.Exception.Message
        }
        [PSCustomObject]@{
          QueryError = $queryError
          Writers    = @($writers | Sort-Object Name)
        } | ConvertTo-Json -Compress -Depth 6
        """
    )
    if not isinstance(raw, dict):
        raise RuntimeError("VSS-Writer-Modul lieferte kein Dictionary zurück.")

    data = ensure_list(raw.get('Writers', []))
    query_error = str(raw.get('QueryError', '') or '').strip()
    issues = []

    if query_error and not data:
        lowered_error = query_error.lower()
        missing_admin = any(token in lowered_error for token in (
            'erforderlichen berechtigungen',
            'erhöhte administratorrechte',
            'access is denied',
            'zugriff verweigert',
            'administrator privileges',
            'administrative privileges',
        ))
        status = 'info' if missing_admin else 'error'
        summary = report_tr("vss_admin_required_summary") if missing_admin else report_tr("vss_read_failed_summary")
        issues = [
            report_tr("vss_admin_required_issue")
            if missing_admin else query_error
        ]
        return make_result(
            'vss_writers',
            'VSS-Writer',
            'Updates & Software',
            174,
            'table',
            [],
            status=status,
            summary=summary,
            issues=issues,
            description=report_tr("vss_description"),
        )

    def _state_is_stable(value: Any) -> bool:
        text = str(value or '').strip().lower()
        return text in {'stable', 'stabil', 'keine fehler', 'no error'} or text.startswith('stable ') or text.startswith('stabil ')

    bad = [w for w in data if str(w.get('LastError', '') or '').strip() and str(w.get('LastError', '') or '').strip().lower() not in {'no error', 'kein fehler', 'keine fehler'}]
    waiting = [w for w in data if str(w.get('State', '') or '').strip() and not _state_is_stable(w.get('State'))]

    if bad or waiting:
        status = 'warning'
        summary = f"Writer fehlerhaft/auffällig: {len(bad) + len(waiting)}"
        if bad:
            issues.append(f"{len(bad)} Writer mit Fehlerstatus erkannt.")
        if waiting:
            issues.append(f"{len(waiting)} Writer nicht im Zustand Stable/Stabil.")
    else:
        status = 'ok' if data else 'info'
        summary = f"{len(data)} VSS-Writer gelesen | keine Auffälligkeiten" if data else 'Keine VSS-Writer-Daten gefunden'

    if query_error:
        issues.append(f"Teilweise unvollständige VSS-Abfrage: {query_error}")

    return make_result(
        'vss_writers',
        'VSS-Writer',
        'Updates & Software',
        174,
        'table',
        data,
        status=status,
        summary=summary,
        issues=issues,
        description=report_tr("vss_description"),
    )


def collect_route_table() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            $routes = @()
            try {
              foreach ($r in @(Get-NetRoute -AddressFamily IPv4 -ErrorAction Stop)) {
                $routes += [PSCustomObject]@{
                  DestinationPrefix = [string]$r.DestinationPrefix
                  NextHop = [string]$r.NextHop
                  RouteMetric = [int]$r.RouteMetric
                  InterfaceAlias = [string]$r.InterfaceAlias
                  State = [string]$r.State
                }
              }
            } catch {
              foreach ($r in @(route print -4 | Out-String -Stream)) { }
            }
            $routes | Sort-Object DestinationPrefix, RouteMetric | Select-Object -First 120 | ConvertTo-Json -Compress
            """
        )
    )
    default_routes = [r for r in data if str(r.get('DestinationPrefix','')).strip() == '0.0.0.0/0']
    issues=[]
    status='ok'
    if len(default_routes) > 1:
        status='info'
        issues.append(f"Mehrere Default-Routen erkannt: {len(default_routes)}")
    summary = f"{len(data)} IPv4-Routen | Default-Routen: {len(default_routes)}"
    return make_result(
        'route_table',
        'Routingtabelle',
        'Netzwerk',
        175,
        'table',
        data,
        status=status,
        summary=summary,
        issues=issues,
        description='Aktive IPv4-Routen mit Gateways, Metriken und Adaptern.',
    )


def collect_partitions_detail() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            Get-Partition | ForEach-Object {
              $p = $_
              $v = Get-Volume -Partition $p -ErrorAction SilentlyContinue
              [PSCustomObject]@{
                Disk = $p.DiskNumber
                Partition = $p.PartitionNumber
                DriveLetter = $p.DriveLetter
                SizeGB = [math]::Round($p.Size / 1GB, 2)
                Type = $p.Type
                FileSystem = if ($v) { $v.FileSystem } else { '' }
                FileSystemLabel = if ($v) { $v.FileSystemLabel } else { '' }
                HealthStatus = if ($v) { $v.HealthStatus } else { '' }
              }
            } | Sort-Object Disk, Partition | ConvertTo-Json -Compress
            """
        )
    )
    summary = f"{len(data)} Partition(en) über alle Datenträger"
    return make_result(
        'partitions_detail',
        'Partitionen / Volumes',
        'Inventar & Tiefeninfos',
        176,
        'table',
        data,
        status='info',
        summary=summary,
        description='Partitionen mit Laufwerk, Dateisystem und Gesundheitsstatus.',
    )


def collect_local_users() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            Get-LocalUser | Sort-Object Name | Select-Object Name, Enabled, LastLogon, PasswordExpires, PasswordRequired, Description | ConvertTo-Json -Compress
            """
        )
    )
    enabled = len([u for u in data if u.get('Enabled') is True])
    summary = f"{len(data)} lokale Benutzer | aktiv: {enabled}"
    return make_result(
        'local_users',
        'Lokale Benutzer',
        'Benutzer & Last',
        177,
        'table',
        data,
        status='info',
        summary=summary,
        description='Lokale Benutzerkonten mit Status und letzter Anmeldung.',
    )


def collect_smb_mappings() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            Get-SmbMapping | Select-Object LocalPath, RemotePath, Status, UserName | ConvertTo-Json -Compress
            """
        )
    )
    summary = f"{len(data)} SMB-Mapping(s) / Netzlaufwerk(e)"
    return make_result(
        'smb_mappings',
        'SMB-Mappings / Netzlaufwerke',
        'Netzwerk',
        178,
        'table',
        data,
        status='info',
        summary=summary,
        description='Verbundene Netzlaufwerke und ihre aktuellen SMB-Zielpfade.',
    )


def collect_dns_cache() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            Get-DnsClientCache -ErrorAction SilentlyContinue | Sort-Object Entry -Unique | Select-Object -First 120 Entry, Type, Status, Data, TimeToLive | ConvertTo-Json -Compress
            """
        )
    )
    summary = f"{len(data)} DNS-Cache-Einträge angezeigt"
    return make_result(
        'dns_cache',
        'DNS-Client-Cache',
        'Netzwerk',
        179,
        'table',
        data,
        status='info',
        summary=summary,
        description='Zuletzt aufgelöste DNS-Einträge des lokalen Systems.',
    )


def collect_credential_inventory() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            $text = cmdkey /list 2>$null | Out-String
            if (-not $text.Trim()) {
              @() | ConvertTo-Json -Compress
              return
            }

            $entries = @()
            $current = [ordered]@{}
            foreach ($line in ($text -split "`r?`n")) {
              if ($line -match '^\s*$') {
                if ($current.Count -gt 0) {
                  $entries += [PSCustomObject]$current
                  $current = [ordered]@{}
                }
                continue
              }

              if ($line -match '^\s*(Target|Ziel):\s*(.+)$') {
                $current.TargetName = $matches[2].Trim()
                continue
              }
              if ($line -match '^\s*(Type|Typ):\s*(.+)$') {
                $current.CredentialType = $matches[2].Trim()
                continue
              }
              if ($line -match '^\s*(User|Benutzer):\s*(.+)$') {
                $current.CredentialUser = $matches[2].Trim()
                continue
              }
            }
            if ($current.Count -gt 0) {
              $entries += [PSCustomObject]$current
            }

            $entries | ForEach-Object {
              [PSCustomObject]@{
                TargetName = [string]($_.TargetName)
                CredentialType = [string]($_.CredentialType)
                CredentialUser = [string]($_.CredentialUser)
                IsGeneric = [bool](([string]($_.CredentialType) -match 'generic|generisch') -or ([string]($_.TargetName) -match '^LegacyGeneric:'))
              }
            } | Sort-Object -Property @{Expression='IsGeneric'; Descending=$true}, @{Expression='TargetName'; Ascending=$true} | ConvertTo-Json -Compress
            """
        )
    )
    generic_count = len([item for item in data if item.get('IsGeneric') is True])
    users = sorted({str(item.get('CredentialUser', '')).strip() for item in data if str(item.get('CredentialUser', '')).strip()})
    summary = f"{len(data)} Credential-Einträge | generisch: {generic_count} | Benutzer: {len(users)}"
    return make_result(
        'credential_inventory',
        'Anmeldeinformationen (ohne Geheimnisse)',
        'Benutzer & Last',
        179,
        'table',
        data,
        status='info',
        summary=summary,
        description='Inventarliste aus der Anmeldeinformationsverwaltung mit Ziel und Benutzer, jedoch ohne Passwörter oder geheime Inhalte.',
    )

def collect_wlan_profiles() -> dict[str, Any]:
    data = ensure_list(
        powershell_json(
            r"""
            $base = Join-Path $env:ProgramData 'Microsoft\Wlansvc\Profiles\Interfaces'
            if (-not (Test-Path $base)) {
              @() | ConvertTo-Json -Compress
              return
            }

            $nsUri = 'http://www.microsoft.com/networking/WLAN/profile/v1'
            $items = @()
            Get-ChildItem -Path $base -Filter *.xml -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
              try {
                [xml]$xml = Get-Content -Path $_.FullName -Raw -Encoding UTF8
                $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
                $ns.AddNamespace('w', $nsUri)

                $profileName = $xml.SelectSingleNode('/w:WLANProfile/w:name', $ns)
                $ssidName = $xml.SelectSingleNode('/w:WLANProfile/w:SSIDConfig/w:SSID/w:name', $ns)
                $connectionMode = $xml.SelectSingleNode('/w:WLANProfile/w:connectionMode', $ns)
                $connectionType = $xml.SelectSingleNode('/w:WLANProfile/w:connectionType', $ns)
                $auth = $xml.SelectSingleNode('/w:WLANProfile/w:MSM/w:security/w:authEncryption/w:authentication', $ns)
                $enc = $xml.SelectSingleNode('/w:WLANProfile/w:MSM/w:security/w:authEncryption/w:encryption', $ns)
                $nonBroadcast = $xml.SelectSingleNode('/w:WLANProfile/w:SSIDConfig/w:nonBroadcast', $ns)
                $autoSwitch = $xml.SelectSingleNode('/w:WLANProfile/w:autoSwitch', $ns)

                $items += [PSCustomObject]@{
                  ProfileName = if ($profileName) { [string]$profileName.InnerText } else { '' }
                  SSIDName = if ($ssidName) { [string]$ssidName.InnerText } else { '' }
                  ConnectionMode = if ($connectionMode) { [string]$connectionMode.InnerText } else { '' }
                  ConnectionType = if ($connectionType) { [string]$connectionType.InnerText } else { '' }
                  Authentication = if ($auth) { [string]$auth.InnerText } else { '' }
                  Encryption = if ($enc) { [string]$enc.InnerText } else { '' }
                  IsHidden = if ($nonBroadcast) { [string]$nonBroadcast.InnerText } else { '' }
                  AutoSwitch = if ($autoSwitch) { [string]$autoSwitch.InnerText } else { '' }
                }
              } catch {}
            }

            $items | Sort-Object ProfileName, SSIDName -Unique | ConvertTo-Json -Compress
            """
        )
    )
    summary = f"{len(data)} gespeicherte WLAN-Profil(e)"
    return make_result(
        'wlan_profiles',
        'WLAN-Profile (ohne Schlüssel)',
        'Netzwerk',
        179,
        'table',
        data,
        status='info',
        summary=summary,
        description='Gespeicherte WLAN-Profile mit SSID, Authentifizierung und Verschlüsselung, aber ohne Klartext-Schlüssel.',
    )

MODULES: list[tuple[str, Callable[[], dict[str, Any]]]] = [
    ("Systeminfo", collect_systeminfo_summary),
    ("Systemprofil / Gerätetyp", collect_system_profile),
    ("Betriebssystem", collect_os_version),
    ("Windows-Aktivierung", collect_activation_status),
    ("Join-Status", collect_join_status),
    ("Identität / Rechtekontext", collect_identity_context),
    ("Kerberos-Tickets", collect_kerberos_tickets),
    ("Uptime", collect_uptime),
    ("CPU", collect_cpu),
    ("Arbeitsspeicher", collect_memory),
    ("Datenträger", collect_disk),
    ("Physische Datenträger / SMART / Medientyp", collect_physical_disks),
    ("Hardware- / Geräte-IDs", collect_hardware_identity_ids),
    ("Hardware / Treiber-Basischeck", collect_hardware_drivers),
    ("Netzwerkadapter", collect_network),
    ("Externe Internet-IP", collect_external_ip),
    ("Netzwerk vertiefen", collect_network_deep),
    ("Routingtabelle", collect_route_table),
    ("SMB-Mappings / Netzlaufwerke", collect_smb_mappings),
    ("DNS-Client-Cache", collect_dns_cache),
    ("WLAN-Profile (ohne Schlüssel)", collect_wlan_profiles),
    ("Anmeldeinformationen (ohne Geheimnisse)", collect_credential_inventory),
    ("Freigegebene Ordner / SMB-Basischeck", collect_shares),
    ("Remote-Zugriff", collect_remote_access),
    ("Zeitdienst / NTP", collect_time_service),
    ("Zertifikate", collect_certificates),
    ("Firewall", collect_firewall),
    ("BitLocker & TPM", collect_bitlocker_tpm),
    ("Defender-Signaturen", collect_defender_signatures),
    ("Antivirus-Schutz", collect_defender),
    ("Offene Ports", collect_ports),
    ("Reboot erforderlich", collect_pending_reboot),
    ("Verfügbare Windows-Updates", collect_available_updates),
    ("Installierte Software", collect_installed_software),
    ("Installierte Updates", collect_installed_updates),
    ("Microsoft Office", collect_office),
    ("Installierte Drucker", collect_printers),
    ("Rollen / Features auf Servern", collect_server_roles_features),
    ("DNS-/DHCP-Basischeck", collect_dns_dhcp_basis),
    ("AD-Server / DC-Basischeck", collect_ad_dc_basis),
    ("IIS-Webserver-Basischeck", collect_iis_webserver_basis),
    ("Lokale Administratoren / privilegierte Gruppen", collect_local_admins),
    ("Lokale Benutzer", collect_local_users),
    ("Aktive Benutzer", collect_active_users),
    ("Benutzerprofile unter C:\\Users", collect_user_profiles_dirs),
    ("Top-Prozesse", collect_top_processes),
    ("Prozesse mit Diensten", collect_process_services_map),
    ("Wichtige Dienste", collect_services),
    ("Geplante Tasks (Windows vs. eigene)", collect_scheduled_tasks),
    ("gpresult /r", collect_gpresult_summary),
    ("Eventlog-Kurzcheck", collect_eventlogs),
    ("VSS-Writer", collect_vss_writers),
    ("Partitionen / Volumes", collect_partitions_detail),
]


def compute_overall_status(results: list[dict[str, Any]]) -> str:
    statuses = [item["status"] for item in results]
    if "error" in statuses:
        return "critical"
    if "critical" in statuses:
        return "critical"
    if "warning" in statuses:
        return "warning"
    if "ok" in statuses:
        return "ok"
    return "info"


def collect_top_issues(results: list[dict[str, Any]]) -> list[str]:
    weighted: list[tuple[int, str]] = []

    for result in results:
        status = str(result.get("status", "info"))
        priority = STATUS_PRIORITY.get(status, 0)

        for issue in result.get("issues", []):
            weighted.append((priority, f"{result['title']}: {issue}"))

    if not weighted:
        return [tr("no_critical")]

    weighted.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in weighted[:10]]


def group_health_status(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    items = []
    for label, categories in HEALTH_GROUPS:
        relevant = [r["status"] for r in results if r["category"] in categories]
        status = highest_status(relevant) if relevant else "info"
        items.append({"label": label, "status": status})
    return items


def get_result_by_id(results: list[dict[str, Any]], module_id: str) -> dict[str, Any] | None:
    for item in results:
        if str(item.get("id", "")) == module_id:
            return item
    return None


def severity_rank(value: str) -> int:
    return {"error": 5, "critical": 4, "warning": 3, "info": 2, "ok": 1}.get(str(value), 0)


def priority_label_for_severity(severity: str) -> str:
    key = {
        "error": "priority_high",
        "critical": "priority_high",
        "warning": "priority_medium",
        "info": "priority_low",
        "ok": "priority_low",
    }.get(str(severity), "priority_low")
    return tr(key)


def compute_health_score(results: list[dict[str, Any]], analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    counts = {key: 0 for key in ("critical", "warning", "error", "info", "ok")}
    for item in results:
        status = str(item.get("status", "info"))
        if status in counts:
            counts[status] += 1

    patterns = ensure_list((analysis or {}).get("patterns", []))
    critical_patterns = sum(1 for item in patterns if str(item.get("severity", "warning")) in {"critical", "error"})
    warning_patterns = sum(1 for item in patterns if str(item.get("severity", "warning")) == "warning")
    info_patterns = sum(1 for item in patterns if str(item.get("severity", "warning")) == "info")

    penalties = {
        "error": min(36, counts["error"] * 18),
        "critical": min(34, counts["critical"] * 14),
        "warning": min(24, counts["warning"] * 7),
        "info": min(8, counts["info"]),
        "patterns": min(18, critical_patterns * 6 + warning_patterns * 3 + info_patterns),
    }
    score = max(0, 100 - sum(penalties.values()))

    if score >= 90:
        label = tr("health_score_very_good")
        status = "ok"
    elif score >= 75:
        label = tr("health_score_good")
        status = "ok"
    elif score >= 50:
        label = tr("health_score_attention")
        status = "warning"
    else:
        label = tr("health_score_critical_label")
        status = "critical"

    return {
        "score": score,
        "label": label,
        "status": status,
        "counts": counts,
        "pattern_count": len(patterns),
        "critical_pattern_count": critical_patterns,
    }


def build_history_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    history_result = get_result_by_id(results, "history_compare") or {}
    data = history_result.get("data", {}) if isinstance(history_result.get("data"), dict) else {}

    has_previous = bool(data.get("Previous_Report_Found"))
    previous_generated_at = str(data.get("Previous_Generated_At", "") or "").strip()
    new_warning_count = len(ensure_list(data.get("New_Warning_Modules", [])))
    resolved_count = len(ensure_list(data.get("Resolved_Warning_Modules", [])))
    new_software_count = len(ensure_list(data.get("New_Software", [])))
    new_port_count = len(ensure_list(data.get("New_Visible_Ports", [])))
    new_share_count = len(ensure_list(data.get("New_Shares", [])))

    if not has_previous:
        trend_key = "no_baseline"
        trend_status = "info"
    elif new_warning_count or new_port_count or new_share_count:
        trend_key = "degraded"
        trend_status = "warning"
    elif resolved_count:
        trend_key = "improved"
        trend_status = "ok"
    elif new_software_count:
        trend_key = "changed"
        trend_status = "info"
    else:
        trend_key = "stable"
        trend_status = "ok"

    return {
        "has_previous": has_previous,
        "previous_generated_at": previous_generated_at,
        "trend_key": trend_key,
        "trend_label": tr(f"health_trend_{trend_key}"),
        "trend_status": trend_status,
        "summary": tr(f"health_trend_summary_{trend_key}"),
        "new_warning_count": new_warning_count,
        "resolved_count": resolved_count,
        "new_software_count": new_software_count,
        "new_port_count": new_port_count,
        "new_share_count": new_share_count,
    }


def build_admin_actions(analysis: dict[str, Any], history_summary: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for pattern in ensure_list(analysis.get("patterns", [])):
        severity = str(pattern.get("severity", "warning"))
        why_items = [localize_text(item) for item in ensure_list(pattern.get("why", [])) if str(item).strip()]
        step_items = [localize_text(item) for item in ensure_list(pattern.get("next_steps", [])) if str(item).strip()]
        related_modules = [localize_text(item) for item in ensure_list(pattern.get("related_modules", [])) if str(item).strip()]
        actions.append({
            "title": localize_text(pattern.get("title", "")),
            "severity": severity,
            "priority_label": priority_label_for_severity(severity),
            "summary": why_items[0] if why_items else localize_text(pattern.get("confidence", "")),
            "context": why_items[:3],
            "steps": step_items[:4],
            "modules": related_modules[:5],
        })

    if history_summary.get("has_previous") and any(history_summary.get(key, 0) for key in ("new_warning_count", "new_port_count", "new_share_count", "new_software_count")):
        history_steps: list[str] = []
        if history_summary.get("new_warning_count"):
            history_steps.append(f"{tr('health_trend_new_warnings')}: {history_summary['new_warning_count']}")
        if history_summary.get("resolved_count"):
            history_steps.append(f"{tr('health_trend_resolved')}: {history_summary['resolved_count']}")
        if history_summary.get("new_software_count"):
            history_steps.append(f"{tr('health_trend_new_software')}: {history_summary['new_software_count']}")
        if history_summary.get("new_port_count"):
            history_steps.append(f"{tr('health_trend_new_ports')}: {history_summary['new_port_count']}")
        if history_summary.get("new_share_count"):
            history_steps.append(f"{tr('health_trend_new_shares')}: {history_summary['new_share_count']}")
        history_severity = "warning" if history_summary.get("new_warning_count") or history_summary.get("new_port_count") or history_summary.get("new_share_count") else "info"
        actions.append({
            "title": tr("checklist_generated_history_title"),
            "severity": history_severity,
            "priority_label": priority_label_for_severity(history_severity),
            "summary": tr("checklist_generated_history_summary"),
            "context": [history_summary.get("summary", "")],
            "steps": history_steps,
            "modules": [translate_title("Historie / Vergleich zum letzten Lauf")],
        })

    actions.sort(key=lambda item: (severity_rank(item.get("severity", "info")), len(item.get("steps", []))), reverse=True)
    return actions


def derive_report_identity(results: list[dict[str, Any]]) -> tuple[str, str]:
    hostname = "Unbekannt"
    os_name = "Unbekannt"

    systeminfo = get_result_by_id(results, "systeminfo_summary") or {}
    sys_data = systeminfo.get("data", {})
    if isinstance(sys_data, dict):
        hostname = str(sys_data.get("HostName", "") or hostname)

    os_result = get_result_by_id(results, "os_version") or {}
    os_data = os_result.get("data", {})
    if isinstance(os_data, dict):
        os_name = str(os_data.get("OS_Name", "") or os_name)

    return hostname, os_name


def build_phase_metadata(phase_mode: str, source_path: str = "") -> dict[str, Any]:
    is_reanalysis = phase_mode == "reanalyze_json"
    analysis_enabled = phase_mode not in {"collect_export"}

    return {
        "selected_mode": phase_mode,
        "selected_mode_label": phase_mode_label(phase_mode),
        "source_label": phase_tr("phase_source_json") if is_reanalysis else phase_tr("phase_source_live"),
        "source_path": source_path,
        "export_label": phase_tr("phase_export_value"),
        "analysis_enabled": analysis_enabled,
        "items": [
            {
                "id": "phase1",
                "title": phase_tr("phase_1_title"),
                "status": "loaded" if is_reanalysis else "completed",
                "status_label": phase_tr("phase_status_loaded") if is_reanalysis else phase_tr("phase_status_completed"),
                "note": phase_tr("phase_note_snapshot"),
            },
            {
                "id": "phase2",
                "title": phase_tr("phase_2_title"),
                "status": "completed" if analysis_enabled else "skipped",
                "status_label": phase_tr("phase_status_completed") if analysis_enabled else phase_tr("phase_status_skipped"),
                "note": phase_tr("phase_note_analysis") if analysis_enabled else phase_tr("phase_note_analysis_skipped"),
            },
            {
                "id": "phase3",
                "title": phase_tr("phase_3_title"),
                "status": "prepared",
                "status_label": phase_tr("phase_status_prepared"),
                "note": phase_tr("phase_note_export"),
            },
        ],
    }


def _event_keyword_hits(results: list[dict[str, Any]], keywords: list[str]) -> list[str]:
    matches: list[str] = []
    event_result = get_result_by_id(results, "eventlogs")
    if not event_result:
        return matches
    rows = ensure_list(event_result.get("data", []))
    normalized = [k.lower() for k in keywords]
    for row in rows:
        provider = str(row.get("ProviderName", "") or "").strip()
        message = str(row.get("Message", "") or "").strip()
        haystack = f"{provider} {message}".lower()
        if any(keyword in haystack for keyword in normalized):
            label = provider or message[:80]
            if label and label not in matches:
                matches.append(label)
    return matches


def _event_keyword_details(results: list[dict[str, Any]], keywords: list[str], limit: int = 3) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    seen: set[str] = set()
    event_result = get_result_by_id(results, "eventlogs")
    if not event_result:
        return matches
    rows = ensure_list(event_result.get("data", []))
    normalized = [k.lower() for k in keywords]
    for row in rows:
        provider = str(row.get("ProviderName", "") or "").strip()
        message = str(row.get("Message", "") or "").strip()
        haystack = f"{provider} {message}".lower()
        if not any(keyword in haystack for keyword in normalized):
            continue
        event_id = str(row.get("Id", "") or "").strip()
        level = str(row.get("LevelDisplayName", "") or "").strip()
        time_created = str(row.get("TimeCreated", "") or "").strip()
        dedupe_key = f"{provider}|{event_id}|{message}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        matches.append({
            "provider": provider,
            "event_id": event_id,
            "level": level,
            "time_created": time_created,
            "message": message,
        })
        if len(matches) >= limit:
            break
    return matches


def _add_pattern(
    patterns: list[dict[str, Any]],
    pattern_id: str,
    title: str,
    severity: str,
    confidence: str,
    why: list[str],
    next_steps: list[str],
    commands: list[str],
    related_modules: list[str],
    derivation: list[str] | None = None,
    interpretation: list[str] | None = None,
    command_details: list[dict[str, str]] | None = None,
) -> None:
    severity_score = {"critical": 4, "warning": 3, "info": 2, "ok": 1}.get(severity, 0)
    confidence_score = {"hoch": 3, "mittel": 2, "niedrig": 1, "high": 3, "medium": 2, "low": 1}.get(confidence.lower(), 1)
    pattern = {
        "id": pattern_id,
        "title": title,
        "severity": severity,
        "confidence": confidence,
        "why": why,
        "next_steps": next_steps,
        "commands": commands,
        "related_modules": related_modules,
        "sort_key": (severity_score, confidence_score, len(why)),
    }
    if derivation:
        pattern["derivation"] = derivation
    if interpretation:
        pattern["interpretation"] = interpretation
    if command_details:
        pattern["command_details"] = command_details
    patterns.append(pattern)


def build_analysis_data(results: list[dict[str, Any]], analysis_enabled: bool = True) -> dict[str, Any]:
    counts = {key: 0 for key in ("critical", "warning", "error", "info", "ok")}
    for item in results:
        status = str(item.get("status", "info"))
        if status in counts:
            counts[status] += 1

    if not analysis_enabled:
        return {
            "enabled": False,
            "counts": counts,
            "patterns": [],
            "solution_plan": [],
            "summary_text": phase_tr("analysis_skipped"),
        }

    patterns: list[dict[str, Any]] = []

    join_result = get_result_by_id(results, "join_status") or {}
    join_data = join_result.get("data", {}) if isinstance(join_result.get("data"), dict) else {}
    part_of_domain = bool(join_data.get("PartOfDomain", False))
    hybrid_join = bool(join_data.get("HybridJoin", False))
    domain_name = str(join_data.get("Domain", "") or "").strip()

    time_result = get_result_by_id(results, "time_service") or {}
    kerberos_result = get_result_by_id(results, "kerberos_tickets") or {}
    gpresult_result = get_result_by_id(results, "gpresult_summary") or {}
    network_result = get_result_by_id(results, "network") or {}
    remote_result = get_result_by_id(results, "remote_access") or {}
    pending_reboot_result = get_result_by_id(results, "pending_reboot") or {}
    updates_result = get_result_by_id(results, "available_updates") or {}
    firewall_result = get_result_by_id(results, "firewall") or {}
    defender_result = get_result_by_id(results, "defender") or {}
    defender_sig_result = get_result_by_id(results, "defender_signatures") or {}
    local_admins_result = get_result_by_id(results, "local_admins") or {}
    disk_result = get_result_by_id(results, "disk") or {}
    physical_disks_result = get_result_by_id(results, "physical_disks") or {}
    vss_result = get_result_by_id(results, "vss_writers") or {}
    ad_dc_result = get_result_by_id(results, "ad_dc_basis") or {}
    dns_dhcp_result = get_result_by_id(results, "dns_dhcp_basis") or {}
    event_hits_auth = _event_keyword_hits(results, ["kerberos", "kdc", "netlogon", "trust relationship", "anmeldung", "logon"])
    event_hits_update = _event_keyword_hits(results, ["windows update", "cbs", "servicing", "wuauserv", "update"])
    event_hits_disk = _event_keyword_hits(results, ["disk", "ntfs", "stor", "volsnap", "vss"])

    time_problem = str(time_result.get("status", "ok")) in {"warning", "critical", "error"}
    kerberos_problem = str(kerberos_result.get("status", "ok")) in {"warning", "critical", "error"}
    gp_problem = str(gpresult_result.get("status", "ok")) in {"warning", "critical", "error"}
    update_problem = str(updates_result.get("status", "ok")) in {"warning", "critical", "error"}
    reboot_problem = str(pending_reboot_result.get("status", "ok")) in {"warning", "critical", "error"}
    security_problem = any(str(r.get("status", "ok")) in {"warning", "critical", "error"} for r in (firewall_result, defender_result, defender_sig_result))
    disk_problem = any(str(r.get("status", "ok")) in {"warning", "critical", "error"} for r in (disk_result, physical_disks_result, vss_result))
    dc_problem = any(str(r.get("status", "ok")) in {"warning", "critical", "error"} for r in (ad_dc_result, dns_dhcp_result))
    auth_live_problem = time_problem or kerberos_problem or gp_problem or dc_problem

    if (part_of_domain or hybrid_join) and auth_live_problem:
        why = []
        if part_of_domain:
            domain_suffix = f" ({domain_name})" if domain_name else ""
            why.append(report_tr("analysis_domain_member", domain_suffix=domain_suffix))
        if hybrid_join:
            why.append(report_tr("analysis_hybrid_join_active"))
        if time_problem:
            why.append(localize_text(str(time_result.get("summary", report_tr("analysis_time_service_default")))))
        if kerberos_problem:
            why.append(localize_text(str(kerberos_result.get("summary", report_tr("analysis_kerberos_default")))))
        if gp_problem:
            why.append(localize_text(str(gpresult_result.get("summary", report_tr("analysis_gpresult_default")))))
        if event_hits_auth:
            why.append(report_tr("analysis_eventlog_matches", items=", ".join(event_hits_auth[:3])))

        derivation: list[str] = []
        interpretation: list[str] = []
        command_details = [
            {"command": "w32tm /query /status", "reason": report_tr("pattern_auth_time_domain_cmd_reason_1")},
            {"command": "w32tm /resync", "reason": report_tr("pattern_auth_time_domain_cmd_reason_2")},
            {"command": report_tr("pattern_auth_time_domain_command_3"), "reason": report_tr("pattern_auth_time_domain_cmd_reason_3")},
            {"command": "klist", "reason": report_tr("pattern_auth_time_domain_cmd_reason_4")},
            {"command": "gpresult /r", "reason": report_tr("pattern_auth_time_domain_cmd_reason_5")},
            {"command": "ipconfig /all", "reason": report_tr("pattern_auth_time_domain_cmd_reason_6")},
        ]
        event_detail_auth: list[dict[str, str]] = []
        event_detail_seen: set[str] = set()
        for keyword_group in (
            ["netlogon", "kerberos", "kdc", "trust relationship", "anmeldung", "logon"],
            ["time-service", "ntpclient", "w32time"],
            ["dns"],
        ):
            for detail in _event_keyword_details(results, keyword_group, limit=3):
                detail_key = f"{detail.get('provider', '')}|{detail.get('event_id', '')}|{detail.get('message', '')}"
                if detail_key in event_detail_seen:
                    continue
                event_detail_seen.add(detail_key)
                event_detail_auth.append(detail)
                if len(event_detail_auth) >= 4:
                    break
            if len(event_detail_auth) >= 4:
                break

        if part_of_domain:
            domain_suffix = f" ({domain_name})" if domain_name else ""
            derivation.append(report_tr("analysis_derivation_domain_member", domain_suffix=domain_suffix))
        if hybrid_join:
            derivation.append(report_tr("analysis_derivation_hybrid_join"))

        time_summary = localize_text(str(time_result.get("summary", report_tr("analysis_time_service_default"))))
        kerberos_summary = localize_text(str(kerberos_result.get("summary", report_tr("analysis_kerberos_default"))))
        gp_summary = localize_text(str(gpresult_result.get("summary", report_tr("analysis_gpresult_default"))))

        if time_summary:
            derivation.append(report_tr("analysis_derivation_module", module=localize_text(str(time_result.get("title", "Zeitdienst / NTP"))), value=time_summary))
        if kerberos_summary:
            derivation.append(report_tr("analysis_derivation_module", module=localize_text(str(kerberos_result.get("title", "Kerberos-Tickets"))), value=kerberos_summary))
        if gp_problem and gp_summary:
            derivation.append(report_tr("analysis_derivation_module", module=localize_text(str(gpresult_result.get("title", "gpresult / r"))), value=gp_summary))
        if event_detail_auth:
            derivation.append(report_tr("analysis_derivation_event_scope"))
            for detail in event_detail_auth:
                derivation.append(
                    report_tr(
                        "analysis_derivation_event",
                        provider=detail.get("provider", ""),
                        event_id=detail.get("event_id", ""),
                        level=detail.get("level", ""),
                        time_created=detail.get("time_created", ""),
                        message=detail.get("message", ""),
                    )
                )

        interpretation.append(report_tr("pattern_auth_time_domain_interp_correlation"))
        if time_problem:
            interpretation.append(report_tr("pattern_auth_time_domain_interp_time_problem", status=time_summary))
        else:
            interpretation.append(report_tr("pattern_auth_time_domain_interp_time_ok", status=time_summary))
        if kerberos_problem:
            interpretation.append(report_tr("pattern_auth_time_domain_interp_kerberos", status=kerberos_summary))

        auth_signal_count = sum(1 for flag in (time_problem, kerberos_problem, gp_problem, dc_problem) if flag)
        auth_severity = "critical" if auth_signal_count >= 2 or (time_problem and event_hits_auth) else "warning"
        auth_confidence = report_tr("confidence_high") if auth_signal_count >= 2 else report_tr("confidence_medium")

        _add_pattern(
            patterns,
            "auth_time_domain",
            report_tr("pattern_auth_time_domain_title"),
            auth_severity,
            auth_confidence,
            why,
            [
                report_tr("pattern_auth_time_domain_step_1"),
                report_tr("pattern_auth_time_domain_step_2"),
                report_tr("pattern_auth_time_domain_step_3"),
                report_tr("pattern_auth_time_domain_step_4"),
            ],
            [item["command"] for item in command_details],
            ["Join-Status", "Zeitdienst / NTP", "Kerberos-Tickets", "gpresult /r", "Eventlog-Kurzcheck"],
            derivation=derivation,
            interpretation=interpretation,
            command_details=command_details,
        )

    if reboot_problem or update_problem:
        why = []
        if reboot_problem:
            why.append(localize_text(str(pending_reboot_result.get("summary", report_tr("analysis_pending_reboot_default")))))
        if update_problem:
            why.append(localize_text(str(updates_result.get("summary", report_tr("analysis_windows_update_default")))))
        if event_hits_update:
            why.append(report_tr("analysis_eventlog_matches", items=", ".join(event_hits_update[:3])))
        _add_pattern(
            patterns,
            "update_servicing",
            report_tr("pattern_update_servicing_title"),
            "critical" if reboot_problem and update_problem else "warning",
            report_tr("confidence_high") if reboot_problem and update_problem else report_tr("confidence_medium"),
            why,
            [
                report_tr("pattern_update_servicing_step_1"),
                report_tr("pattern_update_servicing_step_2"),
                report_tr("pattern_update_servicing_step_3"),
                report_tr("pattern_update_servicing_step_4"),
            ],
            [
                "Get-ItemProperty HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired",
                "Get-WindowsUpdateLog",
                "DISM /Online /Cleanup-Image /ScanHealth",
                "sfc /scannow",
            ],
            ["Neustartstatus", "Verfügbare Windows-Updates", "Eventlog-Kurzcheck", "Datenträger"],
        )

    if security_problem or str(local_admins_result.get("status", "ok")) in {"warning", "critical", "info"}:
        why = []
        if str(firewall_result.get("status", "ok")) in {"warning", "critical", "error"}:
            why.append(localize_text(str(firewall_result.get("summary", report_tr("analysis_firewall_default")))))
        if str(defender_result.get("status", "ok")) in {"warning", "critical", "error"}:
            why.append(localize_text(str(defender_result.get("summary", report_tr("analysis_antivirus_default")))))
        if str(defender_sig_result.get("status", "ok")) in {"warning", "critical", "error"}:
            why.append(localize_text(str(defender_sig_result.get("summary", report_tr("analysis_defender_signatures_default")))))
        if str(local_admins_result.get("status", "ok")) in {"warning", "critical", "info"}:
            why.append(localize_text(str(local_admins_result.get("summary", report_tr("analysis_privileged_groups_default")))))
        if why:
            _add_pattern(
                patterns,
                "security_hardening",
                report_tr("pattern_security_hardening_title"),
                "critical" if str(firewall_result.get("status", "ok")) == "critical" else "warning",
                report_tr("confidence_medium"),
                why,
                [
                    report_tr("pattern_security_hardening_step_1"),
                    report_tr("pattern_security_hardening_step_2"),
                    report_tr("pattern_security_hardening_step_3"),
                ],
                [
                    "Get-NetFirewallProfile",
                    "Get-MpComputerStatus",
                    "Get-LocalGroupMember -Group Administrators",
                    "netstat -ano",
                ],
                ["Firewall", "Antivirus-Schutz", "Defender-Signaturen", "Lokale Administratoren / privilegierte Gruppen"],
            )

    if disk_problem:
        why = []
        for result in (disk_result, physical_disks_result, vss_result):
            if str(result.get("status", "ok")) in {"warning", "critical", "error"}:
                why.append(localize_text(str(result.get("summary", report_tr("analysis_storage_default")))))
        if event_hits_disk:
            why.append(report_tr("analysis_eventlog_matches", items=", ".join(event_hits_disk[:3])))
        if why:
            _add_pattern(
                patterns,
                "storage_backup_health",
                report_tr("pattern_storage_backup_health_title"),
                "critical" if str(physical_disks_result.get("status", "ok")) in {"critical", "error"} else "warning",
                report_tr("confidence_medium"),
                why,
                [
                    report_tr("pattern_storage_backup_health_step_1"),
                    report_tr("pattern_storage_backup_health_step_2"),
                    report_tr("pattern_storage_backup_health_step_3"),
                ],
                [
                    "Get-Volume",
                    "Get-PhysicalDisk",
                    "vssadmin list writers",
                    "Get-WinEvent -LogName System -MaxEvents 50",
                ],
                ["Datenträger", "Physische Datenträger / SMART / Medientyp", "VSS-Writer", "Eventlog-Kurzcheck"],
            )

    if str(remote_result.get("status", "ok")) in {"warning", "critical"}:
        why = [localize_text(str(remote_result.get("summary", report_tr("analysis_remote_access_default"))))]
        network_rows = ensure_list(network_result.get("data", []))
        if network_rows:
            first_dns = str(network_rows[0].get("DNS_Server", "") or "").strip()
            if first_dns:
                why.append(report_tr("analysis_dns_servers", dns=first_dns))
        _add_pattern(
            patterns,
            "remote_access",
            report_tr("pattern_remote_access_title"),
            "warning",
            report_tr("confidence_medium"),
            why,
            [
                report_tr("pattern_remote_access_step_1"),
                report_tr("pattern_remote_access_step_2"),
            ],
            [
                "Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server'",
                "Get-ChildItem WSMan:\\localhost\\Listener",
                "Get-NetFirewallRule",
            ],
            ["Remote-Zugriff", "Firewall", "Netzwerkadapter"],
        )

    if dc_problem:
        why = []
        if str(ad_dc_result.get("status", "ok")) in {"warning", "critical", "error"}:
            why.append(localize_text(str(ad_dc_result.get("summary", report_tr("analysis_ad_dc_default")))))
        if str(dns_dhcp_result.get("status", "ok")) in {"warning", "critical", "error"}:
            why.append(localize_text(str(dns_dhcp_result.get("summary", report_tr("analysis_dns_dhcp_default")))))
        _add_pattern(
            patterns,
            "server_role_health",
            report_tr("pattern_server_role_health_title"),
            "warning",
            report_tr("confidence_medium"),
            why,
            [
                report_tr("pattern_server_role_health_step_1"),
                report_tr("pattern_server_role_health_step_2"),
            ],
            [
                "Get-Service NTDS,DFSR,Netlogon,Kdc,ADWS,DNS",
                "Get-DnsServerZone",
                "Get-DhcpServerv4Scope",
            ],
            ["AD-Server / DC-Basischeck", "DNS-/DHCP-Basischeck"],
        )

    services_result = get_result_by_id(results, "services") or {}
    if str(services_result.get("status", "ok")) in {"warning", "critical", "error", "info"}:
        service_rows = [row for row in ensure_list(services_result.get("data", [])) if isinstance(row, dict)]
        service_findings = []
        critical_service_count = 0
        for row in service_rows:
            finding = str(row.get("__row_status", row.get("FindingSeverity", "")) or "").strip().lower()
            if finding not in {"critical", "warning", "info"}:
                continue
            display_name = str(row.get("DisplayName", "") or row.get("Name", "") or localize_text("Dienst")).strip()
            expected = str(row.get("Erwartet", "") or "").strip()
            start_type = str(row.get("StartType", "") or "").strip()
            svc_status = str(row.get("Status", "") or "").strip()
            service_findings.append(report_tr("analysis_service_mismatch", service=display_name, expected=localize_text(expected), start_type=localize_text(start_type), svc_status=localize_text(svc_status)))
            if finding == "critical":
                critical_service_count += 1

        if service_findings:
            _add_pattern(
                patterns,
                "service_starttype_alignment",
                report_tr("pattern_service_starttype_alignment_title"),
                "critical" if critical_service_count else "warning",
                report_tr("confidence_high") if critical_service_count else report_tr("confidence_medium"),
                service_findings[:5],
                [
                    report_tr("pattern_service_starttype_alignment_step_1"),
                    report_tr("pattern_service_starttype_alignment_step_2"),
                    report_tr("pattern_service_starttype_alignment_step_3"),
                    report_tr("pattern_service_starttype_alignment_step_4"),
                ],
                [
                    "Get-CimInstance Win32_Service | Select-Object Name, StartMode, State, DisplayName",
                    "Get-Service <Dienstname>",
                    "sc qc <Dienstname>",
                    "Get-WinEvent -LogName System -MaxEvents 100 | Where-Object {$_.ProviderName -match 'Service Control Manager'}",
                ],
                ["Wichtige Dienste", "Eventlog-Kurzcheck"],
            )

    certificates_result = get_result_by_id(results, "certificates") or {}
    if str(certificates_result.get("status", "ok")) in {"warning", "critical", "error", "info"}:
        certificate_rows = [row for row in ensure_list(certificates_result.get("data", [])) if isinstance(row, dict)]
        certificate_findings = []
        expired_count = 0
        for row in certificate_rows:
            row_severity = str(row.get("__row_status", row.get("status", "")) or "").strip().lower()
            status_text = str(row.get("status", "") or "").strip()
            if row_severity not in {"critical", "warning", "expired", "abgelaufen", "bald ablaufend", "expiring soon"}:
                continue
            subject = str(row.get("subject", "") or localize_text("Zertifikat")).strip()
            valid_until = str(row.get("valid_until", "") or row.get("NotAfter", "") or "").strip()
            certificate_findings.append(report_tr("analysis_certificate_item", subject=subject, valid_until=valid_until or "?", status=localize_text(status_text or row_severity)))
            if row_severity in {"critical", "expired", "abgelaufen"}:
                expired_count += 1

        if certificate_findings:
            why = [localize_text(str(certificates_result.get("summary", report_tr("analysis_certificates_default"))))]
            why.extend(certificate_findings[:4])
            _add_pattern(
                patterns,
                "certificate_health",
                report_tr("pattern_certificate_health_title"),
                "critical" if expired_count else "warning",
                report_tr("confidence_high") if expired_count else report_tr("confidence_medium"),
                why,
                [
                    report_tr("pattern_certificate_health_step_1"),
                    report_tr("pattern_certificate_health_step_2"),
                    report_tr("pattern_certificate_health_step_3"),
                ],
                [
                    r"Get-ChildItem Cert:\LocalMachine\My | Select-Object Subject, NotAfter, Thumbprint",
                    "certutil -store my",
                    r"Get-ChildItem IIS:\SslBindings",
                    r"Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name SSLCertificateSHA1Hash",
                ],
                ["Zertifikate", "Remote-Zugriff"],
            )

    patterns.sort(key=lambda item: item.get("sort_key", (0, 0, 0)), reverse=True)
    for item in patterns:
        item.pop("sort_key", None)

    critical_patterns = [pattern for pattern in patterns if str(pattern.get("severity", "warning")) == "critical"]

    solution_plan: list[dict[str, Any]] = []
    seen_steps: set[str] = set()
    for pattern in critical_patterns:
        for step in pattern.get("next_steps", []):
            step_key = step.strip().lower()
            if not step_key or step_key in seen_steps:
                continue
            seen_steps.add(step_key)
            solution_plan.append({
                "step": step,
                "source_pattern": pattern.get("title", ""),
                "severity": pattern.get("severity", "warning"),
            })

    summary_text = phase_tr("analysis_no_patterns") if not patterns else phase_tr("analysis_no_critical_patterns") if not critical_patterns else ""
    return {
        "enabled": True,
        "counts": counts,
        "patterns": patterns,
        "critical_patterns": critical_patterns,
        "solution_plan": solution_plan,
        "summary_text": summary_text,
    }


def enrich_report_with_phases(report: dict[str, Any], phase_mode: str = "full", source_path: str = "") -> dict[str, Any]:
    results = [item for item in ensure_list(report.get("results", [])) if isinstance(item, dict)]
    report["results"] = results
    hostname, os_name = derive_report_identity(results)
    report["app_title"] = str(report.get("app_title", APP_TITLE) or APP_TITLE)
    report["hostname"] = str(report.get("hostname", "") or hostname)
    report["os_name"] = str(report.get("os_name", "") or os_name)
    report["generated_at"] = str(report.get("generated_at", "") or now_str())
    report["overall_status"] = compute_overall_status(results)
    report["health"] = group_health_status(results)
    report["top_issues"] = collect_top_issues(results)
    report["phase_mode"] = phase_mode
    report["phases"] = build_phase_metadata(phase_mode, source_path)
    report["analysis"] = build_analysis_data(results, analysis_enabled=(phase_mode != "collect_export"))
    report["health_score"] = compute_health_score(results, report["analysis"])
    report["history_summary"] = build_history_summary(results)
    report["admin_actions"] = build_admin_actions(report["analysis"], report["history_summary"])
    return report


def rebuild_report_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    report = dict(snapshot) if isinstance(snapshot, dict) else {}
    if not isinstance(report.get("results"), list):
        report["results"] = []
    report["generated_at"] = now_str()
    return enrich_report_with_phases(report, phase_mode="reanalyze_json", source_path=str(snapshot.get("_source_path", "") or ""))


def render_scalar(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def is_probably_long_text(value: Any) -> bool:
    text = str(value or "")
    return len(text) > 140 or "\n" in text


def is_technical_field(key: str) -> bool:
    k = str(key).lower()
    markers = [
        "id", "guid", "path", "pnp", "serial", "productcode", "subkey",
        "instance", "device", "port", "mac", "uuid", "bios", "driver",
        "interface", "key", "source", "message", "text", "logonserver"
    ]
    return any(marker in k for marker in markers)


def render_value_cell(key: str, value: Any) -> str:
    text = "" if value is None else str(value)

    if isinstance(value, bool):
        cls = "pill-true" if value else "pill-false"
        label = tr("yes") if value else tr("no")
        return f"<span class='pill {cls}'>{label}</span>"

    if text == "":
        return "<span class='muted'>—</span>"

    if not is_technical_field(key):
        text = localize_text(text)
    escaped = html.escape(text)

    if is_probably_long_text(value):
        return f"<div class='text-block'>{escaped}</div>"

    if is_technical_field(key):
        return f"<code class='inline-code'>{escaped}</code>"

    return escaped


def render_stat_chips(data: dict[str, Any]) -> str:
    chips = []
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            continue
        if value in ("", None, [], {}):
            continue
        value_text = value
        if CURRENT_LANG == "en" and not is_technical_field(str(key)) and isinstance(value, str):
            value_text = localize_text(value)
        chips.append(
            f"<div class='stat-chip'><span>{render_scalar(display_label(key))}</span><strong>{render_scalar(value_text)}</strong></div>"
        )
    if not chips:
        return ""
    return f"<div class='stat-chip-grid'>{''.join(chips)}</div>"


def render_kv_table(data: dict[str, Any]) -> str:
    rows = []
    for key, value in data.items():
        rows.append(
            "<tr>"
            f"<th>{render_scalar(display_label(key))}</th>"
            f"<td>{render_value_cell(str(key), value)}</td>"
            "</tr>"
        )
    return f"<table class='kv-table'>{''.join(rows)}</table>"


def render_list_of_dicts(data: list[dict[str, Any]], context_key: str = "") -> str:
    if not data:
        return "<p class='empty'>" + tr("empty") + "</p>"

    hidden_keys = {"__row_status", "__row_class"}
    keys: list[str] = []
    for row in data:
        for key in row.keys():
            if key in hidden_keys:
                continue
            if key not in keys:
                keys.append(key)

    if context_key == "Software":
        keys = [key for key in keys if key != "RegistryHive"]

    if context_key == "Devices":
        keys = [key for key in keys if key != "Manufacturer"]

    thead = "".join(f"<th>{render_scalar(display_label(key))}</th>" for key in keys)
    body_rows = []

    for row in data:
        cells = "".join(
            f"<td>{render_value_cell(str(key), row.get(key, ''))}</td>"
            for key in keys
        )
        row_status = str(row.get("__row_status", "") or "").strip().lower()
        row_class_extra = str(row.get("__row_class", "") or "").strip()
        row_classes: list[str] = []
        if row_status in {"ok", "info", "warning", "critical", "error"}:
            row_classes.append(f"row-severity-{row_status}")
        if row_class_extra:
            row_classes.append(row_class_extra)
        class_attr = f" class='{' '.join(row_classes)}'" if row_classes else ""
        body_rows.append(f"<tr{class_attr}>{cells}</tr>")

    return (
        "<div class='table-wrap'>"
        f"<table class='data-table'><thead><tr>{thead}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
        "</div>"
    )


def render_data_block(data: Any) -> str:
    if isinstance(data, dict):
        scalar_items = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
        complex_items = {k: v for k, v in data.items() if isinstance(v, (dict, list))}

        blocks = []

        if scalar_items:
            blocks.append(render_stat_chips(scalar_items))
            blocks.append(render_kv_table(scalar_items))

        for key, value in complex_items.items():
            inner = render_data_block(value)

            default_open = str(key) in {
                "BitLocker",
                "TPM",
                "Defender_Status",
                "Details",
                "Updates",
                "Software",
                "VisiblePorts",
                "Shares",
                "Disks",
                "Devices",
                "Adapters",
                "Tasks",
                "Profiles",
                "Printers",
                "DcServices",
                "DcShares",
                "Sites",
                "AppPools",
            }

            open_attr = " open" if default_open else ""

            blocks.append(
                f"<details class='subsection'{open_attr}>"
                f"<summary>{render_scalar(display_label(key))}</summary>"
                f"<div class='subsection-body'>{inner}</div>"
                "</details>"
            )

        return "".join(blocks)

    if isinstance(data, list):
        if not data:
            return "<p class=\'empty\'>" + tr("empty") + "</p>"

        if all(isinstance(item, dict) for item in data):
            return render_list_of_dicts(data)

        items = "".join(f"<li>{render_scalar(item)}</li>" for item in data)
        return f"<ul class='clean-list'>{items}</ul>"

    if isinstance(data, str):
        if is_probably_long_text(data):
            return f"<div class='text-block'>{render_scalar(data)}</div>"
        return f"<pre class='plain-pre'>{render_scalar(data)}</pre>"

    return f"<pre class='plain-pre'>{render_scalar(data)}</pre>"


def get_card_layout_class(result: dict[str, Any]) -> str:
    wide_ids = {
        "ports",
        "network",
        "shares",
        "network_deep",
        "available_updates",
        "disk",
        "installed_software",
        "user_profiles_dirs",
        "physical_disks",
        "hardware_identity_ids",
        "hardware_drivers",
        "printers",
        "scheduled_tasks",
        "gpresult_summary",
        "eventlogs",
        "history_compare",
        "process_services_map",
        "services",
        "route_table",
        "dns_cache",
        "partitions_detail",
        "vss_writers",
        "kerberos_tickets",
        "local_users",
        "credential_inventory",
        "wlan_profiles",
    }

    if result.get("id") in wide_ids:
        return "card-wide"

    return "card-compact"



def get_module_description(result: dict[str, Any]) -> str:
    explicit = str(result.get("description", "") or "").strip()
    if explicit:
        return localize_text(explicit)

    title = str(result.get("title", "") or "").strip()
    category = str(result.get("category", "") or "").strip()

    default_map = {
        "Übersicht": report_tr("module_desc_overview_with_title", title=title.lower()) if title else report_tr("module_desc_overview_default"),
        "Sicherheit": report_tr("module_desc_security_with_title", title=title.lower()) if title else report_tr("module_desc_security_default"),
        "Netzwerk": report_tr("module_desc_network_with_title", title=title.lower()) if title else report_tr("module_desc_network_default"),
        "Updates & Software": report_tr("module_desc_updates_with_title", title=title.lower()) if title else report_tr("module_desc_updates_default"),
        "Benutzer & Last": report_tr("module_desc_userload_with_title", title=title.lower()) if title else report_tr("module_desc_userload_default"),
        "Inventar & Tiefeninfos": report_tr("module_desc_inventory_with_title", title=title.lower()) if title else report_tr("module_desc_inventory_default"),
    }

    return localize_text(default_map.get(category, report_tr("module_desc_generic_with_title", title=title.lower()) if title else report_tr("module_desc_generic_default")))

def render_module_card(result: dict[str, Any]) -> str:
    layout_class = get_card_layout_class(result)
    description_text = get_module_description(result)

    issues_html = ""
    if result.get("issues"):
        issues_items = "".join(f"<li>{render_scalar(localize_text(issue))}</li>" for issue in result["issues"])
        issues_class = "issues issues-info" if result.get("status") == "info" else "issues"
        issues_html = f"<div class='{issues_class}'><strong>{render_scalar(tr('notes'))}</strong><ul>{issues_items}</ul></div>"

    error_html = ""
    if result.get("error"):
        error_html = f"<div class='error-box'>{render_scalar(localize_text(result['error']))}</div>"

    search_blob = " ".join(
        [
            result.get("title", ""),
            result.get("category", ""),
            result.get("summary", ""),
            json.dumps(result.get("data", ""), ensure_ascii=False),
            " ".join(result.get("issues", [])),
        ]
    )

    result_id = render_scalar(result.get("id", ""))

    module_body_html = render_data_block(result.get("data"))

    if result.get("id") == "gpresult_summary":
        module_body_html = f"<div class='gpresult-readable'>{module_body_html}</div>"

    return f"""
    <article class="module-card {layout_class} status-{result['status']}" id="module-{result_id}" data-module-id="{result_id}" data-status="{result['status']}" data-search="{html.escape(search_blob.lower())}">
        <div class="module-head">
            <div class="module-title-wrap">
                <h3>{render_scalar(translate_title(str(result['title'])))}</h3>
                <p class="module-meta">{render_scalar(translate_category(str(result['category'])))} · {format_duration(result['duration_ms'] / 1000)}</p>
            </div>
            <span class="badge badge-{result['status']}">{status_label(result['status'])}</span>
        </div>

        <p class="summary">{render_scalar(localize_text(result.get('summary', '')))}</p>
        {f"<p class='module-description'>{render_scalar(localize_text(description_text))}</p>" if description_text else ''}

        {issues_html}
        {error_html}

        <details class="module-details">
            <summary>{render_scalar(tr("details_show"))}</summary>
            <div class="module-body">
                {module_body_html}
            </div>
        </details>
    </article>
    """


def build_report(results: list[dict[str, Any]], total_seconds: float) -> dict[str, Any]:
    results = list(results)
    results.append(build_history_result(results))

    overall_status = compute_overall_status(results)
    health = group_health_status(results)
    top_issues = collect_top_issues(results)

    hostname = "Unbekannt"
    os_name = "Unbekannt"

    for result in results:
        if result.get("id") == "systeminfo_summary":
            data = result.get("data", {})
            if isinstance(data, dict):
                hostname = str(data.get("HostName", "") or hostname)
        elif result.get("id") == "os_version":
            data = result.get("data", {})
            if isinstance(data, dict):
                os_name = str(data.get("OS_Name", "") or os_name)

    return {
        "app_title": APP_TITLE,
        "generated_at": now_str(),
        "hostname": hostname,
        "os_name": os_name,
        "overall_status": overall_status,
        "total_duration": format_duration(total_seconds),
        "health": health,
        "top_issues": top_issues,
        "results": results,
    }

def render_html_report(report: dict[str, Any]) -> str:
    def get_result_by_id(module_id: str) -> dict[str, Any] | None:
        for item in report["results"]:
            if item.get("id") == module_id:
                return item
        return None

    def build_quick_overview_cards() -> str:
        cpu_result = get_result_by_id("cpu")
        memory_result = get_result_by_id("memory")
        disk_result = get_result_by_id("disk")
        os_result = get_result_by_id("os_version")

        cpu_title = tr("not_available")
        cpu_sub = ""
        if cpu_result and isinstance(cpu_result.get("data"), list) and cpu_result["data"]:
            first_cpu = cpu_result["data"][0]
            cpu_title = str(first_cpu.get("Name", tr("not_available")))
            cpu_sub = f"{first_cpu.get('NumberOfCores', '?')} {"Cores" if CURRENT_LANG == "en" else "Kerne"} / {first_cpu.get('NumberOfLogicalProcessors', '?')} {"Threads" if CURRENT_LANG == "en" else "Threads"}"

        ram_title = tr("not_available")
        ram_sub = ""
        if memory_result and isinstance(memory_result.get("data"), dict):
            ram_total = memory_result["data"].get("Gesamt_GB", "?")
            ram_usage = memory_result["data"].get("Auslastung_Prozent", "?")
            ram_speed = ""
            ram_modules = ensure_list(memory_result["data"].get("RAM_Module_Details", []))
            if ram_modules:
                first_module = ram_modules[0]
                if first_module.get("Speed_MHz"):
                    ram_speed = f"{'Speed' if CURRENT_LANG == 'en' else 'Geschwindigkeit'}: {first_module.get('Speed_MHz')} MT/s"
            ram_title = f"{ram_total} GB"
            ram_sub = ram_speed or (f"Usage: {ram_usage} %" if CURRENT_LANG == "en" else f"Auslastung: {ram_usage} %")

        disk_title = tr("not_available")
        disk_sub = ""
        if disk_result and isinstance(disk_result.get("data"), list) and disk_result["data"]:
            total_gb = sum(safe_float(x.get("Gesamt_GB", 0)) for x in disk_result["data"])
            free_gb = sum(safe_float(x.get("Frei_GB", 0)) for x in disk_result["data"])
            used_gb = round(total_gb - free_gb, 2)
            total_display = round(total_gb, 2)
            disk_title = f"{total_display} GB"
            disk_sub = (f"{used_gb} GB of {total_display} GB used" if CURRENT_LANG == "en" else f"{used_gb} GB von {total_display} GB verwendet")

        os_title = tr("not_available")
        os_sub = ""
        if os_result and isinstance(os_result.get("data"), dict):
            os_title = str(os_result["data"].get("OS_Name", "Nicht verfügbar"))
            os_sub = f"Build {os_result['data'].get('Buildnummer', '?')}"

        cards = [
            f"""
            <div class="quick-card">
                <div class="quick-card-label">{render_scalar("Storage" if CURRENT_LANG == "en" else "Speicher")}</div>
                <div class="quick-card-value">{render_scalar(disk_title)}</div>
                <div class="quick-card-sub">{render_scalar(disk_sub)}</div>
            </div>
            """,
            f"""
            <div class="quick-card">
                <div class="quick-card-label">{render_scalar(tr("quick_os"))}</div>
                <div class="quick-card-value">{render_scalar(os_title)}</div>
                <div class="quick-card-sub">{render_scalar(os_sub)}</div>
            </div>
            """,
            f"""
            <div class="quick-card">
                <div class="quick-card-label">{render_scalar("Installed RAM" if CURRENT_LANG == "en" else "Installierter RAM")}</div>
                <div class="quick-card-value">{render_scalar(ram_title)}</div>
                <div class="quick-card-sub">{render_scalar(ram_sub)}</div>
            </div>
            """,
            f"""
            <div class="quick-card">
                <div class="quick-card-label">{render_scalar("Processor" if CURRENT_LANG == "en" else "Prozessor")}</div>
                <div class="quick-card-value">{render_scalar(cpu_title)}</div>
                <div class="quick-card-sub">{render_scalar(cpu_sub)}</div>
            </div>
            """,
        ]

        return "".join(cards)

    sorted_results = sorted(
        report["results"],
        key=lambda x: (
            CATEGORY_ORDER.index(x["category"]) if x["category"] in CATEGORY_ORDER else 999,
            x["priority"],
        ),
    )

    compact_modules = []
    wide_modules = []

    for result in sorted_results:
        if get_card_layout_class(result) == "card-wide":
            wide_modules.append(result)
        else:
            compact_modules.append(result)

    compact_cards = "".join(render_module_card(module) for module in compact_modules)
    wide_cards = "".join(render_module_card(module) for module in wide_modules)

    category_sections = []

    if compact_cards:
        category_sections.append(
            f"""
            <section class="category-section" id="category-uebersicht">
                <div class="section-head">
                    <h2>{render_scalar(tr("overview"))}</h2>
                </div>
                <div class="module-grid">
                    {compact_cards}
                </div>
            </section>
            """
        )

    if wide_cards:
        category_sections.append(
            f"""
            <section class="category-section" id="category-weitere-informationen">
                <div class="section-head">
                    <h2>{render_scalar(tr("more_info"))}</h2>
                </div>
                <div class="module-grid">
                    {wide_cards}
                </div>
            </section>
            """
        )

    health_cards = "".join(
        f"""
        <div class="health-card status-{item['status']}">
            <div class="health-label">{render_scalar(translate_health_label(item['label']))}</div>
            <div class="health-status">{status_label(item['status'])}</div>
        </div>
        """
        for item in report["health"]
    )

    issues_html = "".join(f"<li>{render_scalar(localize_text(issue))}</li>" for issue in report["top_issues"])

    phase_data = report.get("phases", {}) if isinstance(report.get("phases"), dict) else {}
    phase_cards_html = ""
    for item in ensure_list(phase_data.get("items", [])):
        status_value = str(item.get("status", "info"))
        phase_cards_html += (
            "<article class='phase-card'>"
            f"<div class='phase-card-top'><h3>{render_scalar(item.get('title', ''))}</h3><span class='badge badge-{status_value}'>{render_scalar(item.get('status_label', ''))}</span></div>"
            f"<p>{render_scalar(localize_text(item.get('note', '')))}</p>"
            "</article>"
        )

    phase_meta_html = (
        "<div class='phase-meta-grid'>"
        f"<div class='phase-meta-card'><span>{render_scalar(phase_tr('phase_mode_label'))}</span><strong>{render_scalar(phase_data.get('selected_mode_label', ''))}</strong></div>"
        f"<div class='phase-meta-card'><span>{render_scalar(phase_tr('phase_source_label'))}</span><strong>{render_scalar(phase_data.get('source_label', ''))}</strong></div>"
        f"<div class='phase-meta-card'><span>{render_scalar(phase_tr('phase_export_label'))}</span><strong>{render_scalar(phase_data.get('export_label', ''))}</strong></div>"
        "</div>"
    )
    if phase_data.get('source_path'):
        phase_meta_html += (
            "<div class='phase-source-note'>"
            f"<strong>{render_scalar(phase_tr('analysis_source_path'))}:</strong> {render_scalar(phase_data.get('source_path', ''))}"
            "</div>"
        )

    analysis = report.get("analysis", {}) if isinstance(report.get("analysis"), dict) else {}
    health_score = report.get("health_score", {}) if isinstance(report.get("health_score"), dict) else {}
    history_summary = report.get("history_summary", {}) if isinstance(report.get("history_summary"), dict) else {}
    admin_actions = [item for item in ensure_list(report.get("admin_actions", [])) if isinstance(item, dict)]
    counts = analysis.get("counts", {}) if isinstance(analysis.get("counts"), dict) else {}
    count_labels = {
        'critical': phase_tr('analysis_counts_critical'),
        'warning': phase_tr('analysis_counts_warning'),
        'error': phase_tr('analysis_counts_error'),
        'info': phase_tr('analysis_counts_info'),
        'ok': phase_tr('analysis_counts_ok'),
    }
    count_order = ['critical', 'warning', 'error', 'info', 'ok']
    analysis_counts_html = ''.join(
        f"<div class='analysis-count-card status-{key}'><span>{render_scalar(count_labels[key])}</span><strong>{render_scalar(counts.get(key, 0))}</strong></div>"
        for key in count_order
    )

    visible_patterns = [pattern for pattern in ensure_list(analysis.get("patterns", [])) if isinstance(pattern, dict)]

    pattern_cards_html = ""
    for pattern in visible_patterns:
        why_html = ''.join(f"<li>{render_scalar(localize_text(item))}</li>" for item in ensure_list(pattern.get('why', [])))
        steps_html = ''.join(f"<li>{render_scalar(localize_text(item))}</li>" for item in ensure_list(pattern.get('next_steps', [])))
        if ensure_list(pattern.get('command_details', [])):
            commands_html = ''.join(
                f"<li><code class='inline-code'>{render_scalar(item.get('command', ''))}</code><span class='command-note'>{render_scalar(localize_text(item.get('reason', '')))}</span></li>"
                for item in ensure_list(pattern.get('command_details', []))
            )
        else:
            commands_html = ''.join(f"<li><code class='inline-code'>{render_scalar(item)}</code></li>" for item in ensure_list(pattern.get('commands', [])))
        modules_html = ''.join(f"<li>{render_scalar(localize_text(item))}</li>" for item in ensure_list(pattern.get('related_modules', [])))
        derivation_html = ''.join(f"<li>{render_scalar(localize_text(item))}</li>" for item in ensure_list(pattern.get('derivation', [])))
        interpretation_html = ''.join(f"<li>{render_scalar(localize_text(item))}</li>" for item in ensure_list(pattern.get('interpretation', [])))
        transparency_html = ""
        if derivation_html or interpretation_html:
            transparency_html = (
                f"<div class='diagnosis-grid diagnosis-grid-secondary'>"
                f"<div><h4>{render_scalar(phase_tr('analysis_derivation'))}</h4><ul>{derivation_html}</ul></div>"
                f"<div><h4>{render_scalar(phase_tr('analysis_interpretation'))}</h4><ul>{interpretation_html}</ul></div>"
                f"</div>"
            )
        severity_value = str(pattern.get('severity', 'warning'))
        external_links = build_external_research_links(pattern)
        research_actions_html = (
            "<div class='diagnosis-actions'>"
            f"<a class='mini-action-btn action-link' href='{render_scalar(external_links.get('google_url', 'https://www.google.com/'))}' target='_blank' rel='noopener noreferrer'>{render_scalar(tr('research_google'))}</a>"
            f"<a class='mini-action-btn action-link' href='{render_scalar(external_links.get('gemini_url', f'https://gemini.google.com/?hl={CURRENT_LANG}'))}' target='_blank' rel='noopener noreferrer'>{render_scalar(tr('research_gemini'))}</a>"
            f"<button type='button' class='mini-action-btn ai-copy-btn' data-copy-text='{html.escape(external_links.get('ai_prompt', ''), quote=True)}' data-copied-label='{html.escape(tr('research_prompt_copied'), quote=True)}'>{render_scalar(tr('research_copy_ai_prompt'))}</button>"
            "</div>"
        )
        pattern_cards_html += (
            "<article class='diagnosis-card'>"
            f"<div class='diagnosis-card-top'><div><h3>{render_scalar(localize_text(pattern.get('title', '')))}</h3><p class='diagnosis-confidence'><strong>{render_scalar(tr('diagnosis_priority_label'))}:</strong> {render_scalar(priority_label_for_severity(severity_value))} · <strong>{render_scalar(phase_tr('analysis_confidence'))}:</strong> {render_scalar(localize_text(pattern.get('confidence', '')))}</p></div><div class='diagnosis-card-badges'><span class='badge badge-{render_scalar(severity_value)}'>{render_scalar(status_label(severity_value))}</span><span class='badge badge-neutral'>{render_scalar(priority_label_for_severity(severity_value))}</span></div></div>"
            f"<div class='diagnosis-grid'><div><h4>{render_scalar(phase_tr('analysis_why'))}</h4><ul>{why_html}</ul></div><div><h4>{render_scalar(phase_tr('analysis_steps'))}</h4><ol>{steps_html}</ol></div></div>"
            f"{transparency_html}"
            f"<div class='diagnosis-grid diagnosis-grid-secondary'><div><h4>{render_scalar(phase_tr('analysis_commands'))}</h4><ul class='command-list'>{commands_html}</ul></div><div><h4>{render_scalar(phase_tr('analysis_related_modules'))}</h4><ul>{modules_html}</ul></div></div>"
            f"{research_actions_html}"
            "</article>"
        )

    diagnosis_has_cases = bool(pattern_cards_html)

    if not analysis.get('enabled', False):
        diagnosis_html = f"<div class='panel diagnosis-empty'>{render_scalar(phase_tr('analysis_skipped'))}</div>"
    elif pattern_cards_html:
        solution_plan_html = ''.join(
            f"<li><strong>{render_scalar(localize_text(item.get('step', '')))}</strong><span>{render_scalar(localize_text(item.get('source_pattern', '')))}</span></li>"
            for item in ensure_list(analysis.get('solution_plan', []))
        )
        solution_plan_block = ""
        if solution_plan_html:
            solution_plan_block = (
                f"<aside class='diagnosis-plan'><div class='section-head compact-head'><h3>{render_scalar(phase_tr('analysis_solution_plan'))}</h3></div><div class='panel'><ol class='solution-plan-list'>{solution_plan_html}</ol></div></aside>"
            )
        diagnosis_html = (
            "<div class='analysis-count-grid'>" + analysis_counts_html + "</div>"
            "<div class='diagnosis-section-grid'>"
            f"<div class='diagnosis-patterns'><div class='section-head compact-head'><h3>{render_scalar(phase_tr('analysis_patterns'))}</h3></div>{pattern_cards_html}</div>"
            f"{solution_plan_block}"
            "</div>"
        )
    else:
        diagnosis_html = (
            "<div class='analysis-count-grid'>" + analysis_counts_html + "</div>"
            f"<div class='panel diagnosis-empty'>{render_scalar(localize_text(analysis.get('summary_text', phase_tr('analysis_no_patterns'))))}</div>"
        )

    score_counts = health_score.get("counts", {}) if isinstance(health_score.get("counts"), dict) else {}
    health_score_panel = (
        "<div class='hero-insights-grid'>"
        f"<article class='hero-insight-card score-card score-status-{render_scalar(health_score.get('status', 'info'))}'><div class='hero-insight-head'><div><p class='hero-insight-eyebrow'>{render_scalar(tr('health_score_title'))}</p><h2>{render_scalar(health_score.get('score', 0))}<span>/100</span></h2><p class='hero-insight-summary'>{render_scalar(health_score.get('label', ''))}</p></div><span class='badge badge-{render_scalar(health_score.get('status', 'info'))}'>{render_scalar(health_score.get('label', ''))}</span></div><p class='hero-insight-caption'>{render_scalar(tr('health_score_caption'))}</p><div class='hero-insight-metrics'><div><span>{render_scalar(tr('health_score_critical'))}</span><strong>{render_scalar(score_counts.get('critical', 0) + score_counts.get('error', 0))}</strong></div><div><span>{render_scalar(tr('health_score_warning'))}</span><strong>{render_scalar(score_counts.get('warning', 0))}</strong></div><div><span>{render_scalar(tr('health_score_info'))}</span><strong>{render_scalar(score_counts.get('info', 0))}</strong></div><div><span>{render_scalar(tr('health_score_ok'))}</span><strong>{render_scalar(score_counts.get('ok', 0))}</strong></div></div></article>"
        f"<article class='hero-insight-card trend-card trend-status-{render_scalar(history_summary.get('trend_status', 'info'))}'><div class='hero-insight-head'><div><p class='hero-insight-eyebrow'>{render_scalar(tr('health_trend_title'))}</p><h3>{render_scalar(history_summary.get('trend_label', tr('health_trend_no_baseline')))}</h3><p class='hero-insight-summary'>{render_scalar(history_summary.get('summary', ''))}</p></div><span class='badge badge-{render_scalar(history_summary.get('trend_status', 'info'))}'>{render_scalar(history_summary.get('trend_label', ''))}</span></div><div class='trend-baseline'><span>{render_scalar(tr('health_trend_since'))}</span><strong>{render_scalar(history_summary.get('previous_generated_at', tr('not_available')) if history_summary.get('has_previous') else tr('not_available'))}</strong></div><div class='hero-insight-metrics'><div><span>{render_scalar(tr('health_trend_new_warnings'))}</span><strong>{render_scalar(history_summary.get('new_warning_count', 0))}</strong></div><div><span>{render_scalar(tr('health_trend_resolved'))}</span><strong>{render_scalar(history_summary.get('resolved_count', 0))}</strong></div><div><span>{render_scalar(tr('health_trend_new_ports'))}</span><strong>{render_scalar(history_summary.get('new_port_count', 0))}</strong></div><div><span>{render_scalar(tr('health_trend_new_shares'))}</span><strong>{render_scalar(history_summary.get('new_share_count', 0))}</strong></div></div></article>"
        "</div>"
    )

    generated_checklist_items = []
    for idx, action in enumerate(admin_actions, start=1):
        steps_html = ''.join(f"<li>{render_scalar(step)}</li>" for step in ensure_list(action.get('steps', [])))
        context_html = ''.join(f"<li>{render_scalar(item)}</li>" for item in ensure_list(action.get('context', [])))
        modules_html = ', '.join(render_scalar(item) for item in ensure_list(action.get('modules', [])))
        generated_checklist_items.append(
            "<div class='generated-action generated-action-" + render_scalar(action.get('severity', 'info')) + "'>"
            f"<label class='check-item generated-check-item'><input type='checkbox' data-checklist-group='generated'><span class='generated-action-label'><span class='generated-action-head'><span class='badge badge-{render_scalar(action.get('severity', 'info'))}'>{render_scalar(action.get('priority_label', ''))}</span><strong>{render_scalar(action.get('title', ''))}</strong></span><span class='generated-action-summary'>{render_scalar(action.get('summary', ''))}</span></span></label>"
            + (f"<div class='generated-action-context'><strong>{render_scalar(tr('checklist_generated_context'))}</strong><ul>{context_html}</ul></div>" if context_html else "")
            + (f"<div class='generated-action-steps'><strong>{render_scalar(tr('checklist_generated_steps'))}</strong><ol>{steps_html}</ol></div>" if steps_html else "")
            + (f"<p class='report-help'><strong>{render_scalar(tr('checklist_generated_modules'))}</strong> {modules_html}</p>" if modules_html else "")
            + "</div>"
        )

    generated_checklist_html = (
        "<details class='checklist-group generated-checklist-group' open>"
        f"<summary><span>{render_scalar(tr('checklist_generated_title'))}</span><span class='checklist-count' data-group='generated'>0/{len(generated_checklist_items)}</span></summary>"
        f"<div class='checklist-body'><p class='checklist-example'><strong>{render_scalar(tr('checklist_symptoms_label'))}</strong> {render_scalar(tr('checklist_generated_symptoms'))}</p>"
        + ("".join(generated_checklist_items) if generated_checklist_items else f"<p class='report-help generated-empty'>{render_scalar(tr('checklist_generated_empty'))}</p>")
        + f"<p class='report-help'><strong>{render_scalar(tr('checklist_helpful_label'))}</strong> {render_scalar(tr('checklist_generated_helpful'))}</p></div></details>"
    )

    log_rows = []
    for result in report["results"]:
        result_status = render_scalar(result.get("status", "info"))
        result_id_attr = render_scalar(result.get("id", ""))
        result_title = render_scalar(translate_title(str(result['title'])))
        log_rows.append(
            f"<tr class='row-severity-{result_status}' data-module-id='{result_id_attr}'>"
            f"<td class='runlog-select-cell'><label class='runlog-select-label'><input type='checkbox' class='runlog-module-checkbox' data-module-id='{result_id_attr}' aria-label='{result_title}'><span>{result_title}</span></label></td>"
            f"<td>{render_scalar(translate_category(str(result['category'])))}</td>"
            f"<td><span class='badge badge-{result_status}'>{status_label(result['status'])}</span></td>"
            f"<td>{format_duration(result['duration_ms'] / 1000)}</td>"
            f"<td>{render_scalar(localize_text(result.get('summary', '')))}</td>"
            "</tr>"
        )

    hostname = render_scalar(report.get("hostname", tr("not_available")))
    os_name = render_scalar(report.get("os_name", "Unbekannt"))
    overall_status = str(report.get("overall_status", "info"))
    overall_label = render_scalar(status_label(overall_status))
    generated_at = render_scalar(report.get("generated_at", ""))
    total_duration = render_scalar(report.get("total_duration", ""))
    module_count = str(len(report["results"]))
    quick_overview_cards = build_quick_overview_cards()

    template_path = RESOURCE_DIR / "templates" / "report.html"
    template = template_path.read_text(encoding="utf-8")

    css_path = RESOURCE_DIR / "static" / "css" / "report.css"
    css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    js_path = RESOURCE_DIR / "static" / "js" / "report.js"
    js_content = js_path.read_text(encoding="utf-8") if js_path.exists() else ""

    def get_result(module_id: str) -> dict[str, Any] | None:
        for item in report["results"]:
            if item.get("id") == module_id:
                return item
        return None

    cpu_result = get_result("cpu") or {}
    memory_result = get_result("memory") or {}
    disk_result = get_result("disk") or {}
    uptime_result = get_result("uptime") or {}
    join_result = get_result("join_status") or {}
    external_ip_result = get_result("external_ip") or {}

    cpu_data = cpu_result.get("data", [])
    if isinstance(cpu_data, list) and cpu_data:
        quick_cpu = str(cpu_data[0].get("Name", "Unbekannt"))
    else:
        quick_cpu = "Unbekannt"

    memory_data = memory_result.get("data", {})
    if isinstance(memory_data, dict):
        quick_ram = tr("ram_total_used_fmt").format(total=memory_data.get("Gesamt_GB", "–"), used=memory_data.get("Auslastung_Prozent", "–"))
    else:
        quick_ram = "Unbekannt"

    disk_data = disk_result.get("data", [])
    quick_system_disks_html = ""

    if isinstance(disk_data, list) and disk_data:
        system_disk_items = []

        for entry in disk_data:
            laufwerk = str(entry.get("Laufwerk", "") or "").strip()
            frei_gb = entry.get("Frei_GB", "–")
            gesamt_gb = entry.get("Gesamt_GB", "–")

            if not laufwerk:
                continue

            system_disk_items.append(
                f"<div class='stack-list-item'>{render_scalar(laufwerk)} · {render_scalar(tr('free_space_fmt').format(free=frei_gb, total=gesamt_gb))}</div>"
            )

        if system_disk_items:
            quick_system_disks_html = "".join(system_disk_items)
        else:
            quick_system_disks_html = f"<div class='stack-list-item'>{render_scalar(tr('no_drive_data'))}</div>"
    else:
        quick_system_disks_html = f"<div class='stack-list-item'>{render_scalar(tr('no_drive_data'))}</div>"

    os_result = get_result("os_version") or {}
    os_data = os_result.get("data", {})

    if isinstance(os_data, dict):
        display_version = str(os_data.get("Feature_Update", "") or "").strip()
        build_number = str(os_data.get("Buildnummer", "") or "").strip()

        if display_version and build_number:
            os_version_badge = f"{tr('version_label')} {display_version} · Build {build_number}"
        elif display_version:
            os_version_badge = f"{tr('version_label')} {display_version}"
        elif build_number:
            os_version_badge = f"Build {build_number}"
        else:
            os_version_badge = tr("version_unknown")
    else:
        os_version_badge = tr("version_unknown")

    uptime_data = uptime_result.get("data", {})
    if isinstance(uptime_data, dict):
        quick_uptime = localize_text(str(uptime_data.get("Uptime", tr("not_available"))))
    else:
        quick_uptime = tr("not_available")

    join_data = join_result.get("data", {})
    if isinstance(join_data, dict):
        if join_data.get("HybridJoin"):
            quick_join = f"Hybrid Join | {join_data.get('Domain', '')}"
        elif join_data.get("PartOfDomain"):
            quick_join = f"{tr('join_domain')} | {join_data.get('Domain', '')}"
        elif join_data.get("AzureAdJoined") is True:
            quick_join = "Azure AD Joined"
        else:
            quick_join = f"{tr('join_workgroup')} | {join_data.get('Workgroup', tr('not_available'))}"
    else:
        quick_join = tr("not_available")

    external_ip_data = external_ip_result.get("data", {})
    if isinstance(external_ip_data, dict):
        quick_external_ip = str(external_ip_data.get("ExternalIP", tr("not_available")) or tr("not_available"))
    else:
        quick_external_ip = tr("not_available")

    report_lang = CURRENT_LANG
    replacements = {
        "{{HTML_LANG}}": render_scalar(report_lang),
        "{{LABEL_REPORT_EYEBROW}}": render_scalar(tr("report_eyebrow")),
        "{{LABEL_CREATED}}": render_scalar(tr("created")),
        "{{LABEL_DURATION}}": render_scalar(tr("duration")),
        "{{LABEL_MODULES}}": render_scalar(tr("modules")),
        "{{LABEL_SEARCH}}": render_scalar(tr("search")),
        "{{PLACEHOLDER_SEARCH}}": render_scalar(tr("search_placeholder")),
        "{{LABEL_PROBLEMS_ONLY}}": render_scalar(tr("problems_only")),
        "{{NAV_HEALTH_OVERVIEW}}": render_scalar(tr("health_overview")),
        "{{NAV_PHASES}}": render_scalar(phase_tr("nav_phases")),
        "{{NAV_DIAGNOSIS}}": render_scalar(phase_tr("nav_diagnosis")),
        "{{NAV_RUN_LOG}}": render_scalar(tr("run_log")),
        "{{NAV_OVERVIEW}}": render_scalar(tr("overview")),
        "{{NAV_MORE_INFO}}": render_scalar(tr("more_info")),
        "{{LABEL_STATUS}}": render_scalar(tr("status")),
        "{{LABEL_SHOW_ALL}}": render_scalar(tr("show_all")),
        "{{LABEL_TOP_ISSUES}}": render_scalar(tr("top_issues")),
        "{{FOOTER_GENERATED_WITH}}": render_scalar(tr("footer_generated_with")),
        "{{FOOTER_TOOL}}": render_scalar(tr("footer_tool")),
        "{{FOOTER_LANGUAGE_HINT}}": render_scalar(tr("footer_language_hint")),
        "{{APP_VERSION}}": render_scalar(APP_VERSION),
        "{{APP_BUILD_DATE}}": render_scalar(APP_BUILD_DATE),
        "{{APP_WEBSITE}}": render_scalar(APP_WEBSITE),
        "{{APP_CONTACT_EMAIL}}": render_scalar(APP_CONTACT_EMAIL),
        "{{TITLE}}": render_scalar(APP_TITLE),
        "{{HOSTNAME}}": hostname,
        "{{OS_NAME}}": os_name,
        "{{OVERALL_STATUS}}": overall_status,
        "{{OVERALL_LABEL}}": overall_label,
        "{{GENERATED_AT}}": generated_at,
        "{{TOTAL_DURATION}}": total_duration,
        "{{MODULE_COUNT}}": module_count,
        "{{HEALTH_SCORE_PANEL}}": health_score_panel,
        "{{GENERATED_CHECKLIST_HTML}}": generated_checklist_html,
        "{{QUICK_OVERVIEW_CARDS}}": quick_overview_cards,
        "{{HEALTH_CARDS}}": health_cards,
        "{{PHASE_META_HTML}}": phase_meta_html,
        "{{PHASE_CARDS_HTML}}": phase_cards_html,
        "{{DIAGNOSIS_HTML}}": diagnosis_html,
        "{{DIAGNOSIS_HAS_CASES}}": "true" if diagnosis_has_cases else "false",
        "{{ISSUES_HTML}}": issues_html,
        "{{CATEGORY_SECTIONS}}": "".join(category_sections),
        "{{LOG_ROWS}}": "".join(log_rows),
        "{{QUICK_CPU}}": render_scalar(quick_cpu),
        "{{QUICK_RAM}}": render_scalar(quick_ram),
        "{{QUICK_UPTIME}}": render_scalar(quick_uptime),
        "{{QUICK_EXTERNAL_IP}}": render_scalar(quick_external_ip),
        "{{OS_VERSION_BADGE}}": render_scalar(os_version_badge),
        "{{QUICK_SYSTEM_DISKS}}": quick_system_disks_html,
        "{{CSS_CONTENT}}": css_content,
        "{{LABEL_STATUS_FILTER_ARIA}}": render_scalar(tr("status_filter_aria")),
        "{{LABEL_HERO_COLLAPSE}}": render_scalar(tr("hero_collapse")),
        "{{LABEL_HERO_EXPAND}}": render_scalar(tr("hero_expand")),
        "{{LABEL_CARDS_EXPAND}}": render_scalar(tr("cards_expand")),
        "{{LABEL_CARDS_COLLAPSE}}": render_scalar(tr("cards_collapse")),
        "{{SIDEPANEL_TITLE}}": render_scalar(tr("sidepanel_title")),
        "{{SIDEPANEL_CLOSE_LABEL}}": render_scalar(tr("sidepanel_close")),
        "{{SIDEPANEL_TAB_LABEL}}": render_scalar(tr("sidepanel_tab")),
        "{{CHECKLIST_TAB_LABEL}}": render_scalar(tr("checklist_tab")),
        "{{CHECKLIST_TITLE}}": render_scalar(tr("checklist_title")),
        "{{CHECKLIST_CLOSE_LABEL}}": render_scalar(tr("checklist_close")),
        "{{CHECKLIST_EXPAND_LABEL}}": render_scalar(tr("checklist_expand")),
        "{{CHECKLIST_RESET_LABEL}}": render_scalar(tr("checklist_reset")),
        "{{FILTER_OK}}": render_scalar(tr("filter_ok")),
        "{{FILTER_INFO}}": render_scalar(tr("filter_info")),
        "{{FILTER_WARNING}}": render_scalar(tr("filter_warning")),
        "{{FILTER_CRITICAL}}": render_scalar(tr("filter_critical")),
        "{{FILTER_ERROR}}": render_scalar(tr("filter_error")),
        "{{QUICK_LABEL_HOSTNAME}}": render_scalar(tr("quick_hostname")),
        "{{QUICK_LABEL_OS}}": render_scalar(tr("quick_os")),
        "{{QUICK_LABEL_CPU}}": render_scalar(tr("quick_cpu")),
        "{{QUICK_LABEL_RAM}}": render_scalar(tr("quick_ram")),
        "{{QUICK_LABEL_DRIVES}}": render_scalar(tr("quick_drives")),
        "{{QUICK_LABEL_UPTIME}}": render_scalar(tr("quick_uptime")),
        "{{QUICK_LABEL_EXTERNAL_IP}}": render_scalar(tr("quick_external_ip")),
        "{{CHECKLIST_INTRO_PURPOSE_TITLE}}": render_scalar(tr("checklist_intro_purpose_title")),
        "{{CHECKLIST_INTRO_PURPOSE_TEXT}}": render_scalar(tr("checklist_intro_purpose_text")),
        "{{CHECKLIST_INTRO_NOTE_TITLE}}": render_scalar(tr("checklist_intro_note_title")),
        "{{CHECKLIST_INTRO_NOTE_TEXT}}": render_scalar(tr("checklist_intro_note_text")),
        "{{CHECKLIST_INTRO_ORDER_TITLE}}": render_scalar(tr("checklist_intro_order_title")),
        "{{CHECKLIST_INTRO_ORDER_TEXT}}": render_scalar(tr("checklist_intro_order_text")),
        "{{CHECKLIST_SYMPTOMS_LABEL}}": render_scalar(tr("checklist_symptoms_label")),
        "{{CHECKLIST_HELPFUL_LABEL}}": render_scalar(tr("checklist_helpful_label")),
        "{{CHECKLIST_GROUP_1_TITLE}}": render_scalar(tr("checklist_group_1_title")),
        "{{CHECKLIST_GROUP_1_SYMPTOMS}}": render_scalar(tr("checklist_group_1_symptoms")),
        "{{CHECKLIST_GROUP_1_HELPFUL}}": render_scalar(tr("checklist_group_1_helpful")),
        "{{CHECKLIST_GROUP_1_ITEM_1}}": render_scalar(tr("checklist_group_1_item_1")),
        "{{CHECKLIST_GROUP_1_ITEM_2}}": render_scalar(tr("checklist_group_1_item_2")),
        "{{CHECKLIST_GROUP_1_ITEM_3}}": render_scalar(tr("checklist_group_1_item_3")),
        "{{CHECKLIST_GROUP_1_ITEM_4}}": render_scalar(tr("checklist_group_1_item_4")),
        "{{CHECKLIST_GROUP_2_TITLE}}": render_scalar(tr("checklist_group_2_title")),
        "{{CHECKLIST_GROUP_2_SYMPTOMS}}": render_scalar(tr("checklist_group_2_symptoms")),
        "{{CHECKLIST_GROUP_2_HELPFUL}}": render_scalar(tr("checklist_group_2_helpful")),
        "{{CHECKLIST_GROUP_2_ITEM_1}}": render_scalar(tr("checklist_group_2_item_1")),
        "{{CHECKLIST_GROUP_2_ITEM_2}}": render_scalar(tr("checklist_group_2_item_2")),
        "{{CHECKLIST_GROUP_2_ITEM_3}}": render_scalar(tr("checklist_group_2_item_3")),
        "{{CHECKLIST_GROUP_2_ITEM_4}}": render_scalar(tr("checklist_group_2_item_4")),
        "{{CHECKLIST_GROUP_3_TITLE}}": render_scalar(tr("checklist_group_3_title")),
        "{{CHECKLIST_GROUP_3_SYMPTOMS}}": render_scalar(tr("checklist_group_3_symptoms")),
        "{{CHECKLIST_GROUP_3_HELPFUL}}": render_scalar(tr("checklist_group_3_helpful")),
        "{{CHECKLIST_GROUP_3_ITEM_1}}": render_scalar(tr("checklist_group_3_item_1")),
        "{{CHECKLIST_GROUP_3_ITEM_2}}": render_scalar(tr("checklist_group_3_item_2")),
        "{{CHECKLIST_GROUP_3_ITEM_3}}": render_scalar(tr("checklist_group_3_item_3")),
        "{{CHECKLIST_GROUP_3_ITEM_4}}": render_scalar(tr("checklist_group_3_item_4")),
        "{{CHECKLIST_GROUP_3_ITEM_5}}": render_scalar(tr("checklist_group_3_item_5")),
        "{{CHECKLIST_GROUP_3_ITEM_6}}": render_scalar(tr("checklist_group_3_item_6")),
        "{{CHECKLIST_GROUP_4_TITLE}}": render_scalar(tr("checklist_group_4_title")),
        "{{CHECKLIST_GROUP_4_SYMPTOMS}}": render_scalar(tr("checklist_group_4_symptoms")),
        "{{CHECKLIST_GROUP_4_HELPFUL}}": render_scalar(tr("checklist_group_4_helpful")),
        "{{CHECKLIST_GROUP_4_ITEM_1}}": render_scalar(tr("checklist_group_4_item_1")),
        "{{CHECKLIST_GROUP_4_ITEM_2}}": render_scalar(tr("checklist_group_4_item_2")),
        "{{CHECKLIST_GROUP_4_ITEM_3}}": render_scalar(tr("checklist_group_4_item_3")),
        "{{CHECKLIST_GROUP_4_ITEM_4}}": render_scalar(tr("checklist_group_4_item_4")),
        "{{CHECKLIST_GROUP_4_ITEM_5}}": render_scalar(tr("checklist_group_4_item_5")),
        "{{CHECKLIST_GROUP_5_TITLE}}": render_scalar(tr("checklist_group_5_title")),
        "{{CHECKLIST_GROUP_5_SYMPTOMS}}": render_scalar(tr("checklist_group_5_symptoms")),
        "{{CHECKLIST_GROUP_5_HELPFUL}}": render_scalar(tr("checklist_group_5_helpful")),
        "{{CHECKLIST_GROUP_5_ITEM_1}}": render_scalar(tr("checklist_group_5_item_1")),
        "{{CHECKLIST_GROUP_5_ITEM_2}}": render_scalar(tr("checklist_group_5_item_2")),
        "{{CHECKLIST_GROUP_5_ITEM_3}}": render_scalar(tr("checklist_group_5_item_3")),
        "{{CHECKLIST_GROUP_5_ITEM_4}}": render_scalar(tr("checklist_group_5_item_4")),
        "{{CHECKLIST_GROUP_5_ITEM_5}}": render_scalar(tr("checklist_group_5_item_5")),
        "{{CHECKLIST_GROUP_5_ITEM_6}}": render_scalar(tr("checklist_group_5_item_6")),
        "{{RUNLOG_MODULE}}": render_scalar(tr("runlog_module")),
        "{{RUNLOG_CATEGORY}}": render_scalar(tr("runlog_category")),
        "{{RUNLOG_STATUS}}": render_scalar(tr("status")),
        "{{RUNLOG_DURATION}}": render_scalar(tr("runlog_duration")),
        "{{RUNLOG_SUMMARY}}": render_scalar(tr("runlog_summary")),
        "{{RUNLOG_FILTER_TITLE}}": render_scalar(tr("runlog_filter_title")),
        "{{RUNLOG_FILTER_HINT}}": render_scalar(tr("runlog_filter_hint")),
        "{{RUNLOG_RESET_SELECTION}}": render_scalar(tr("runlog_reset_selection")),
        "{{RUNLOG_SELECTED_COUNT}}": render_scalar(tr("runlog_selected_count")),
        "{{JS_CONTENT}}": js_content,
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)

    return template

def main() -> int:
    if not is_windows():
        print(report_tr("tool_windows_only"))
        return 1

    root = tk.Tk()
    root.title(f"{APP_TITLE} - v{APP_VERSION}")
    root.geometry("760x255")
    root.resizable(False, False)
    root.configure(bg="#f0f0f0")

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        try:
            current_theme = style.theme_use()
            if current_theme not in ("vista", "xpnative", "winnative"):
                for candidate in ("vista", "xpnative", "winnative", current_theme):
                    try:
                        style.theme_use(candidate)
                        break
                    except Exception:
                        continue
        except Exception:
            pass

    style.configure("Green.Horizontal.TProgressbar", troughcolor="#e8edf3", background="#2e7d32", lightcolor="#2e7d32", darkcolor="#2e7d32", bordercolor="#d0d7df")
    style.configure("Red.Horizontal.TProgressbar", troughcolor="#e8edf3", background="#c62828", lightcolor="#c62828", darkcolor="#c62828", bordercolor="#d0d7df")

    style.configure("Gui.TFrame", background="#f0f0f0")
    style.configure("Gui.TLabel", background="#f0f0f0", foreground="#000000")

    main_frame = ttk.Frame(root, padding=15, style="Gui.TFrame")
    main_frame.pack(fill="both", expand=True)

    title_label = ttk.Label(main_frame, text=APP_TITLE, font=("Segoe UI", 14, "bold"), style="Gui.TLabel")
    title_label.pack(anchor="w", pady=(0, 10))

    status_var = tk.StringVar(value=tr("gui_ready"))
    info_var = tk.StringVar(value=tr("gui_wait"))
    progress_var = tk.IntVar(value=0)

    status_label = ttk.Label(main_frame, textvariable=status_var, style="Gui.TLabel", wraplength=700, justify="left")
    status_label.pack(fill="x", pady=(0, 8))

    info_label = ttk.Label(main_frame, textvariable=info_var, style="Gui.TLabel", wraplength=700, justify="left")
    info_label.pack(fill="x", pady=(0, 12))

    progress_style_name = "Red.Horizontal.TProgressbar" if is_admin() else "Green.Horizontal.TProgressbar"
    progressbar = ttk.Progressbar(main_frame, maximum=100, variable=progress_var, style=progress_style_name)
    progressbar.pack(fill="x", pady=(0, 12))

    button_frame = tk.Frame(main_frame, bg="#f0f0f0")
    button_frame.pack(fill="x")
    button_frame.grid_columnconfigure(0, weight=0)
    button_frame.grid_columnconfigure(1, weight=1)

    start_button = tk.Button(
        button_frame,
        text=tr("gui_start"),
        bg="#f0f0f0",
        fg="#000000",
        activebackground="#e5e5e5",
        activeforeground="#000000",
        relief="raised",
        bd=1,
        padx=10,
        pady=4,
        highlightthickness=0
    )
    start_button.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="w")

    close_button = tk.Button(
        button_frame,
        text=tr("gui_close"),
        command=root.destroy,
        bg="#f0f0f0",
        fg="#000000",
        activebackground="#e5e5e5",
        activeforeground="#000000",
        relief="raised",
        bd=1,
        padx=10,
        pady=4,
        highlightthickness=0
    )
    close_button.grid(row=0, column=1, sticky="e")

    info_links_frame = ttk.Frame(main_frame, style="Gui.TFrame")
    info_links_frame.pack(fill="x", pady=(10, 0))

    product_info_label = ttk.Label(
        info_links_frame,
        text=f"Version {APP_VERSION} | Build date {APP_BUILD_DATE} | {APP_PRODUCT}",
        style="Gui.TLabel",
        font=("Segoe UI", 8),
    )
    product_info_label.pack(side="left")

    website_button = tk.Button(
        info_links_frame,
        text="Website",
        command=lambda: webbrowser.open(APP_WEBSITE),
        bg="#f0f0f0",
        fg="#0563c1",
        activebackground="#e5e5e5",
        activeforeground="#0563c1",
        relief="flat",
        bd=0,
        padx=8,
        pady=0,
        cursor="hand2",
        highlightthickness=0,
    )
    website_button.pack(side="right", padx=(8, 0))

    contact_button = tk.Button(
        info_links_frame,
        text="Contact",
        command=lambda: webbrowser.open(f"mailto:{APP_CONTACT_EMAIL}"),
        bg="#f0f0f0",
        fg="#0563c1",
        activebackground="#e5e5e5",
        activeforeground="#0563c1",
        relief="flat",
        bd=0,
        padx=8,
        pady=0,
        cursor="hand2",
        highlightthickness=0,
    )
    contact_button.pack(side="right")

    def update_status(text: str):
        root.after(0, lambda: status_var.set(text))

    def update_info(text: str):
        root.after(0, lambda: info_var.set(text))

    def update_progress(index: int, total: int):
        percent = int(index / total * 100) if total else 0
        root.after(0, lambda: progress_var.set(percent))

    def worker(selected_mode: str, source_json_path: str = ""):
        try:
            if is_admin():
                update_info(tr("gui_admin"))
            else:
                update_info(tr("gui_non_admin"))

            started = time.perf_counter()
            report: dict[str, Any]
            total = len(MODULES)
            update_progress(0, total)

            if selected_mode == "reanalyze_json":
                update_status(phase_tr("gui_loading_json"))
                update_progress(1, 3)
                source_path = Path(source_json_path)
                snapshot = json.loads(source_path.read_text(encoding="utf-8"))
                if not isinstance(snapshot, dict):
                    raise RuntimeError(report_tr("invalid_json_report"))
                snapshot["_source_path"] = str(source_path)
                update_status(phase_tr("gui_analyzing"))
                update_progress(2, 3)
                report = rebuild_report_from_snapshot(snapshot)
                report["total_duration"] = format_duration(time.perf_counter() - started)
                update_status(tr("gui_building_html"))
                update_progress(3, 3)
            else:
                results: list[dict[str, Any]] = []
                update_status(tr("gui_starting"))

                for index, (title, func) in enumerate(MODULES, start=1):
                    results.append(
                        collect_module(
                            title,
                            func,
                            index,
                            total,
                            status_callback=update_status,
                            progress_callback=update_progress,
                        )
                    )

                update_status(phase_tr("gui_analyzing") if selected_mode == "full" else tr("gui_building_html"))
                total_seconds = time.perf_counter() - started
                report = build_report(results, total_seconds)
                report = enrich_report_with_phases(report, phase_mode=selected_mode)
                update_status(tr("gui_building_html"))

            safe_hostname = "".join(
                c if c.isalnum() or c in ("-", "_") else "_"
                for c in str(report.get("hostname", "unbekannt"))
            )
            safe_timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            suffix = ""
            if selected_mode == "collect_export":
                suffix = "_snapshot"
            elif selected_mode == "reanalyze_json":
                suffix = "_reanalysis"

            json_output = OUTPUT_DIR / f"report_{safe_hostname}_{safe_timestamp}{suffix}.json"
            html_output = OUTPUT_DIR / f"report_{safe_hostname}_{safe_timestamp}{suffix}.html"

            json_output.write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            html_output.write_text(
                render_html_report(report),
                encoding="utf-8"
            )

            if selected_mode != "reanalyze_json":
                JSON_OUTPUT.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )

            update_progress(total, total)
            update_status(tr("gui_finished"))
            update_info(f"{tr('gui_saved')} {html_output.name}")

            phase_info = report.get("phases", {}) if isinstance(report.get("phases"), dict) else {}
            phase_items = phase_info.get("items", []) if isinstance(phase_info.get("items"), list) else []
            if len(phase_items) >= 3:
                phase_items[2]["status"] = "ok"
                phase_items[2]["status_label"] = phase_tr("phase_status_exported")
                html_output.write_text(
                    render_html_report(report),
                    encoding="utf-8"
                )
                json_output.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                if selected_mode != "reanalyze_json":
                    JSON_OUTPUT.write_text(
                        json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )

            try:
                webbrowser.open(html_output.resolve().as_uri())
            except Exception:
                pass

        except Exception as exc:
            import traceback

            tb = traceback.format_exc()
            print(tb)

            update_status(tr("gui_run_error"))
            update_info(f"{type(exc).__name__}: {exc}")

            try:
                error_output = OUTPUT_DIR / f"error_{dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
                error_output.write_text(tb, encoding="utf-8")
                update_info(f"{type(exc).__name__}: {exc} | Details in: {error_output.name}")
            except Exception:
                pass

        finally:
            root.after(0, lambda: start_button.config(state="normal"))

    def start_run():
        selected_mode = "full"
        source_json_path = ""

        start_button.config(state="disabled")
        progress_var.set(0)
        status_var.set(tr("gui_init"))
        info_var.set(tr("gui_wait_please"))

        threading.Thread(target=worker, args=(selected_mode, source_json_path), daemon=True).start()

    start_button.config(command=start_run)

    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())