## Warhammer 30K / Horus Heresy Units Vocabulary (Version 1)

Scope: Core generic (non-named) units, vehicles, and chassis used across Legiones Astartes in the Age of Darkness. Excludes Primarchs and named characters. Phase 2 gated; requires game_system=warhammer_30k (or specific heresy flag) plus resolved faction/legion context if later added.

Activation: Same gating as other codex unit files (post faction/system resolution; feature flag `enable_unit_extraction=true`). Generic single words ("tactical", "breacher", "support") require adjacency to another qualifying token (e.g., "squad", weapon descriptor) or legion context.

```
codex_units:
	warhammer_30k:
		legiones_astartes:
			tactical_squad: ["tactical_squad", "tactical_marines", "tactical_marine"]
			tactical_support_squad: ["tactical_support", "support_squad", "tactical_support_squad"]
			heavy_support_squad: ["heavy_support_squad", "heavy_support"]
			breacher_squad: ["breacher", "breachers", "breacher_squad"]
			destroyer_squad: ["destroyer_squad", "destroyers", "destroyer_marines"]
			recon_squad: ["recon", "recon_squad"]
			assault_squad: ["assault_squad", "assault_marines"]
			veteran_tactical_squad: ["veteran_tactical", "veteran_tactical_squad", "veterans_tactical"]
			seeker_squad: ["seeker", "seekers", "seeker_squad"]
			support_squad: ["support_squad"]
			terminator_squad: ["terminator", "terminators", "terminator_squad", "cataphractii", "tartaros"]
			apothecary: ["apothecary", "apothecarion"]
			techmarine: ["techmarine", "forge_lord"]
			chaplain: ["chaplain"]
			praetor: ["praetor"]
			centurion: ["centurion"]
			legion_command_squad: ["command_squad", "legion_command", "legion_command_squad"]
			dreadnought: ["dreadnought", "contemptor", "deredeo", "leviathan"]
			jetbike_squad: ["jetbike", "jetbikes", "jetbike_squad", "scimitar_jetbike", "scimitar_jetbikes"]
			outrider_squad: ["outrider", "outriders", "outrider_squad"]
			attack_bike: ["attack_bike", "attack_bikes"]
			speeder_squadron: ["land_speeder", "land_speeders", "speeder", "speeders"]
			kratos_battle_tank: ["kratos", "kratos_battle_tank"]
			sicaran_battle_tank: ["sicaran", "sicaran_tank", "sicaran_battle_tank"]
			predator_tank: ["predator", "predator_tank"]
			land_raider: ["land_raider", "land_raider_proteus", "land_raider_phobos"]
			spartan_assault_tank: ["spartan", "spartan_assault_tank"]
			rhino: ["rhino", "rhinos"]
			proteus_carrier: ["proteus_carrier"]
			damocles_rhino: ["damocles", "damocles_rhino"]
			storm_eagle_gunship: ["storm_eagle", "storm_eagle_gunship"]
			fire_raptor_gunship: ["fire_raptor", "fire_raptor_gunship"]
			sx_destroyer: ["xiphon", "xiphon_interceptor"]
			cerberus_tank_destroyer: ["cerberus", "cerberus_tank_destroyer"]
			typhon_heavy_siege_tank: ["typhon", "typhon_siege_tank", "typhon_heavy_siege_tank"]
			saboteur: ["saboteur"]
			moritat: ["moritat"]
			legion_medicae: ["legion_medicae"]
			legion_heavy_support: ["legion_heavy_support"]
			legion_veterans: ["legion_veteran", "legion_veterans"]
```

TODO: Add legion-specific unique units (Deathwing Companions, Justaerin, Phoenix Terminators, Deathshroud, Gal Vorbak, etc.) in future gated expansion; add Solar Auxilia, Mechanicum, Custodes, Knight Households, Imperial Army once system field reliably distinguishes them.
