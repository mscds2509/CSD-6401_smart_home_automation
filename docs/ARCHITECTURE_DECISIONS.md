# Architecture Decision Records (ADRs)

## ADR-001: Use Bridge for device protocols

**Status:** Accepted  
**Context:** Lights and fans must work over more than one communication protocol (Wi-Fi and MQTT). A protocol change should not require a new device class for every device/protocol combination.  
**Decision:** Keep device abstractions (`LightDevice`, `FanDevice`) separate from protocol implementors (`WifiDriver`, `MqttDriver`) and compose them through `SmartDeviceBridge`.  
**Trade-offs:** This introduces an extra abstraction and driver object, but avoids a class explosion such as `WifiLight`, `MqttLight`, `WifiFan`, and `MqttFan`. It also allows protocols to vary independently from device capabilities.

## ADR-002: Use Decorator for energy monitoring

**Status:** Accepted  
**Context:** Energy measurement is an optional capability that should be added to selected devices without changing their core implementation or forcing every device to carry energy-specific state.  
**Decision:** Wrap a `SmartDevice` in `EnergyMonitoringDecorator`, which forwards device operations and adds energy accounting.  
**Trade-offs:** The wrapper adds a layer and callers may need to know which capabilities are available, but the base device stays focused and the feature can be composed at runtime.

## ADR-003: Use Repository / DAO for persistence boundaries

**Status:** Accepted  
**Context:** SQL statements embedded in application/domain workflows make persistence harder to test and replace.  
**Decision:** Use repository objects with an injected SQLite connection factory for command audit and telemetry persistence.  
**Trade-offs:** There is a small amount of mapping code, but database operations become independently testable and the domain layer does not need to know SQL details.

## ADR-004: Use Strategy for automation conditions

**Status:** Accepted  
**Context:** Automation conditions differ by the data they inspect: daily energy, local time windows, or device ON duration. A single hard-coded condition branch does not scale cleanly.  
**Decision:** Implement interchangeable `Condition` strategies: `EnergyThresholdCondition`, `TimeWindowCondition`, and `AnomalyCondition`. The rule evaluator selects the appropriate strategy from the rule type.  
**Trade-offs:** More condition classes are introduced, but each condition is independently testable and new condition types can be added without rewriting existing condition logic.

## ADR-005: Use periodic polling and a background simulation worker

**Status:** Accepted for prototype  
**Context:** The dashboard needs observable updates while simulated sensors and energy values evolve.  
**Decision:** The browser polls the authenticated state API every 2.5 seconds, while a daemon worker updates simulated telemetry and evaluates data-driven rules every 10 seconds.  
**Trade-offs:** Polling and a local daemon are simple to demonstrate but are not a production message-bus architecture. A deployed system should use a supervised worker, explicit lifecycle management, authentication hardening and potentially SSE/WebSockets.

## ADR-006: Keep a versioned JSON state memento

**Status:** Accepted as a backup/export mechanism  
**Context:** SQLite is the live persistence store, but a portable representation of home settings, device configuration and enabled automation-rule state is useful for review and backup.  
**Decision:** `StateSnapshotStore` writes an atomic, versioned `instance/state.json` snapshot and the authenticated API exposes a download endpoint.  
**Trade-offs:** The JSON snapshot is not a second live database and is not automatically replayed over SQLite; this avoids two competing sources of truth. SQLite remains authoritative for application restarts.
