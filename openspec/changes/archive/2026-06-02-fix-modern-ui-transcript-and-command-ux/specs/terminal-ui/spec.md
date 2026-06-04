## MODIFIED Requirements

### Requirement: Interactive Configuration Reset
Deepy SHALL reset terminal configuration without leaving partial files.

#### Scenario: Reset setup is interrupted
- **WHEN** a user exits or the prompt stream ends during `/reset` setup
- **THEN** Deepy SHALL report the cancellation without printing a traceback
- **AND** if a config file existed before `/reset`, Deepy SHALL restore that
  file unchanged
- **AND** if no config file existed before `/reset`, Deepy SHALL leave no
  partial config file behind

#### Scenario: Reset changes running UI or theme selection
- **WHEN** a user completes `/reset` setup in the stable terminal UI
- **AND** the selected UI or theme differs from the currently running stable UI
  or theme selection
- **THEN** Deepy SHALL tell the user that restarting Deepy is required for the
  UI and theme selection to take effect
