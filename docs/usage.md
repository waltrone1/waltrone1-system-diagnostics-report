# Usage Guide

This document explains the basic usage of **waltrone1 System-Diagnostics-Report**.

waltrone1 System-Diagnostics-Report is a Windows diagnostics and reporting tool by **WALTRONE**.

It is designed to help users, admins and technicians collect important Windows system information in one structured and readable report.

---

## Basic Usage

1. Download the latest release.
2. Extract the ZIP file completely.
3. Start the application.
4. Generate a diagnostics report.
5. Open and review the generated HTML report.
6. Check the overall score and health status.
7. Review warnings, critical findings and detected patterns.
8. Use the diagnosis and action plan section for next steps.
9. Use the admin troubleshooting checklist if further checks are needed.
10. Compare the report with previous runs if history data is available.

---

## Main Workflow

The typical workflow is:

1. Start waltrone1 System-Diagnostics-Report.
2. Generate a new system diagnostics report.
3. Review the system overview and health status.
4. Check warnings, critical findings and detected patterns.
5. Review module results for system, hardware, storage, network and security information.
6. Use the diagnosis and action plan section for recommended next steps.
7. Use the admin troubleshooting checklist for additional manual checks.
8. Save or archive the generated HTML report if needed.
9. Save or reuse JSON snapshot data for later comparison if available.

---

## Report Sections

The generated report may include sections such as:

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

## HTML Report

The HTML report is the main output of the tool.

It can be used for:

- Troubleshooting preparation
- System review
- Technical documentation
- Support requests
- Internal handover workflows
- Before / after comparison
- Archiving system status information

The report is designed to be readable in a normal web browser.

---

## JSON Snapshot

If available, JSON snapshot data can be used for later review or comparison with previous runs.

This can be useful when checking changes after:

- Updates
- Maintenance tasks
- Configuration changes
- Troubleshooting actions
- Migration work
- Security-related changes

---

## Language Options

The application may support German and English language modes.

Example:

```text
-Lang de
-Lang en
```

Use the language option that fits your workflow.

---

## Screenshots

Screenshots are available in the repository under:

```text
screenshots/
```

The main README also includes a visual overview of the application and generated report sections.

---

## Build / Source Notes

The source files are located in:

```text
src/
```

Build-related files for creating a Windows executable are located in:

```text
src/py2exe/
```

Generated build output such as `.exe`, `.zip`, `build/`, `dist/` or release folders should not be committed directly to the repository.

Final release packages should be published through GitHub Releases.

---

## Safety Notes

waltrone1 System-Diagnostics-Report is intended as a local diagnostics and reporting helper tool.

Important notes:

- Use only on systems where you are allowed to run such tools.
- Some information may require Administrator rights for full visibility.
- Some checks may return limited results depending on permissions and system configuration.
- Generated reports may contain sensitive technical information.
- Review reports before sharing them with other people.
- Share generated reports only with authorized persons.
- Always validate findings before taking remediation actions in production environments.
- The tool does not replace professional diagnostics, security auditing or expert review.

---

## Troubleshooting

### The tool does not start

Try the following:

- Extract the ZIP file completely before starting the application.
- Start the application from a local folder.
- Check whether antivirus or Windows SmartScreen blocks the file.
- Test the tool in a separate folder or test environment.
- Run the tool as Administrator if required.

### Some report sections are incomplete

Check the following:

- Run the tool with Administrator rights.
- Check local Windows permissions.
- Check whether security software blocks access to some system information.
- Check whether required Windows components are available.
- Check whether the system is managed by company policies.

Some information may not be available on every Windows system or in every environment.

### Network-related results are incomplete

Check the following:

- Network connectivity
- DNS configuration
- Firewall rules
- VPN status
- Proxy settings
- Local permissions
- Company network policies

Network-related diagnostics depend on the current environment and available permissions.

---

## Disclaimer

This tool is provided as-is, without warranty of any kind.

Use it at your own risk.

The author is not responsible for data loss, system issues, incorrect findings, missed findings, wrong conclusions, production issues or damages caused by the use of this software.
