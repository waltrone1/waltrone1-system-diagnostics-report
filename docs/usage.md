# Usage

This document explains the basic usage of **waltrone1 System-Diagnostics-Report**.

---

## Purpose

**waltrone1 System-Diagnostics-Report** creates a structured Windows diagnostics report.

The tool is designed to help users, admins and technicians collect important system information in one readable report.

The generated report can be useful for troubleshooting, documentation, support requests and system reviews.

---

## Basic Workflow

1. Download the latest release.
2. Extract the ZIP file.
3. Start the application.
4. Generate the diagnostics report.
5. Open and review the generated HTML report.
6. Check the overall score and health status.
7. Review warnings, critical findings and detected patterns.
8. Use the diagnosis and action plan section for next steps.
9. Use the admin troubleshooting checklist if further checks are needed.
10. Compare the report with previous runs if history data is available.

---

## Report Sections

The report may include sections such as:

- Overall score and health status
- System overview
- Hardware information
- Operating system information
- CPU information
- RAM information
- Drive and storage information
- Network information
- Remote access checks
- Security-related checks
- Microsoft Defender / antivirus status
- Windows Update information
- Firewall status
- BitLocker and TPM status
- Installed software overview
- Detected patterns
- Diagnosis and action plan
- Admin troubleshooting checklist
- History comparison

---

## Screenshots

Screenshots are available in the repository under:

```text
screenshots/
```

The main README also includes a visual overview of the application.

---

## Build Notes

The source code is located in:

```text
src/
```

Build-related files for creating a Windows executable are located in:

```text
src/py2exe/
```

Generated files such as `.exe`, `.zip`, `build/`, `dist/` or release folders should not be committed directly to the repository.

Final release packages should be published through GitHub Releases.

---

## Notes

This tool does not replace professional diagnostics software.

It is intended as a simple helper tool for quick system overview, basic documentation and troubleshooting preparation.

---

## Disclaimer

This tool is provided as-is, without warranty of any kind.

Use it at your own risk.

The author is not responsible for data loss, system issues or damages caused by the use of this software.
