# Goal Agent State

## Built
- [2026-08-19 08:46 UTC] G2-1 -- Enemy AI -> AI/SporeborneAIController.h, AI/SporeborneAIController.cpp, Characters/SporeborneEnemyCharacter.h, Characters/SporeborneEnemyCharacter.cpp

## Decisions
- [2026-08-19 08:46 UTC] G2-1: The feature is a minimal but genuinely fun enemy AI that satisfies G2 ('one room is genuinely fun to clear'). It consists of two tightly-coupled classes: ASporeborneAIController (a ticker-based state machine with Idle/Chase/Attack states driven by distance) and ASporeborneEnemyCharacter (health, melee attack via UGameplayStatics::ApplyDamage, and a ragdoll death). The controller auto-possesses any placed or spawned enemy. Parameters (detection range, attack range, cooldown, damage, health) are all EditDefaultsOnly so a designer can tune them in the Blueprint subclass without touching code. Two engine modules beyond the base four are needed: AIModule (for AAIController and MoveToActor) and NavigationSystem (for the nav-mesh path-finding that MoveToActor relies on).
- [2026-08-19 08:46 UTC] !! ACTION REQUIRED for G2-1: add module dependency: AIModule, NavigationSystem
- [2026-08-19 09:07 UTC] Post-generation compile of G2-1 failed on two real bugs, both fixed by hand: (1) the agent used bare subfolder includes ("AI/Foo.h") but this module's actual /I search path is Source/ not Source/Sporeborne_Rogue/, confirmed against the compiler .rsp -- fixed by prefixing with the module name ("Sporeborne_Rogue/AI/Foo.h") in both .cpp files; (2) SetCollisionEnabled() was called through GetCapsuleComponent(), whose return type is only forward-declared in Character.h -- fixed by adding #include "Components/CapsuleComponent.h". Both lessons were folded into build_codegen_prompt() so future runs should not repeat them. Compile now succeeds (Build.bat, Sporeborne_RogueEditor, Development, Win64 -- Result: Succeeded).

## Next
- G1-2 (score=0.750): jump
- G1-4 (score=0.750): dodge-with-i-frames
- G4-3 (score=0.725): boss
- G2-2 (score=0.692): telegraphed projectiles
- G1-3 (score=0.670): attack combo
