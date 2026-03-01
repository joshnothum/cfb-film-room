# Known Data Caveats

## CFB 26 Defensive Playbook Mapping (Revisit Required)

- Date logged: 2026-03-01
- Context:
  - `cfb.fan` appears to retain legacy CFB 25-style defensive playbook organization.
  - Defensive scheme slugs may not cleanly match CFB 26 in-game playbook structure.
  - Example risk: `3-3-5-tite-def` and `3-3-5` may be merged in-game, while `cfb.fan` still separates them and labels many plays as `NEW IN 26`.
- Current impact:
  - Not blocking current coach-feedback MVP.
  - May cause noisy or misleading scheme-level assumptions when mapping team defense identity.
- Required follow-up:
  1. Validate in-game defensive playbook taxonomy for CFB 26.
  2. Build a canonical scheme mapping layer (site slug -> normalized in-game scheme).
  3. Reconcile duplicate/merged scheme families before scaling automated analysis.
