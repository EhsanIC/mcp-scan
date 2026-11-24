Checklist item	Scanner check
Tool Description Verification (Medium)	Look for injection phrases, hidden Unicode, or hidden tags like <SECRET> in descriptions
Function Name Checking / Conflict Detection (High)	Find duplicate or look-alike tool names across servers
Version Control (Medium)	Hash tool descriptions and alert when they change
Input Validation (High)	Flag schemas with loose or dangerous parameters (command, path, url, no constraints)
Tool Permission Control / Behavior Constraints (High)	Flag tools with shell, file, or network power
Mandatory Authentication (High)	Check whether a remote server answers without credentials
Encrypted Communication / Certificate Validation (High)	Check that remote servers use valid TLS
Dependency Management / Package Integrity (High)	Check packages against vulnerability databases

The checklist's "Information Transparency" item is useful too, since it specifically mentions hidden tags like <SECRET> in tool tex
