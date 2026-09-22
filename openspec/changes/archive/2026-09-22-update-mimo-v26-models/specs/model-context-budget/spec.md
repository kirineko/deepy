## MODIFIED Requirements

### Requirement: Model Limit Evidence
Deepy SHALL distinguish documented model limits, conservative runtime limits and unverified proxy limits for each supported provider/model/API combination.

#### Scenario: Model has only a nominal window
- **WHEN** official documentation reports 1M without an established exact token count
- **THEN** Deepy SHALL use a conservative 1,000,000-token runtime window and label it as conservative
- **AND** it SHALL NOT claim 1,048,576 is verified from that notation

#### Scenario: CLI Proxy models
- **WHEN** the selected model is one of the five supported CLI Proxy models
- **THEN** Deepy SHALL record the OpenAI 1,050,000 context and 128,000 output reference limits
- **AND** it SHALL distinguish those from the unverified proxy limits and apply any smaller configured cap

#### Scenario: MiMo V2.6 documented limits
- **WHEN** limits are resolved for `mimo-v2.6-flash` or `mimo-v2.6-pro` through Responses
- **THEN** Deepy SHALL record a nominal 1M context, conservative 1,000,000-token runtime window and documented 131,072-token maximum output
- **AND** it SHALL retain the official documentation source and evidence check date
- **AND** it SHALL NOT present these limits as successful maximum-capacity live probes

#### Scenario: MiMo default and configured output budgets
- **WHEN** a main MiMo V2.6 request has no configured output override
- **THEN** Deepy SHALL retain its 32,768-token default output budget
- **AND** configured output budgets up to 131,072 SHALL be accepted when the effective context window and safety reserve permit them
- **AND** output budgets above 131,072 SHALL be rejected without saving invalid configuration
