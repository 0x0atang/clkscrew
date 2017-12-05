# CLKscrew: Exposing the Perils of Security-Oblivious Energy Management
This repository contains alpha-version code to explore the use of CLKscrew on ARM-based SoCs.

We only include the code used for the RSA signature attack scenario, and only for the Nexus 6 device.



## Repository Content
| Component     | Description   |
| ------------- | ------------- |
| pycrypto      | Python script to generate self-signed update blob  |
| faultmin_SD805      | Minimal POC code to test fault occurrence on SnapDragon 805 SoC  |
| dofever      | Simple compute-heavy program to raise core temperature  |
| clkHarness      | Python scaffolding harness to run experiments  |


## References
1. [CLKSCREW: Exposing the Perils of Security-Oblivious Energy Management. In 26th USENIX Security Symposium. (USENIX Security 2017)](https://www.usenix.org/conference/usenixsecurity17/technical-sessions/presentation/tang)
