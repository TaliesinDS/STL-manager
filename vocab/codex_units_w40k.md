## Warhammer 40K Codex Units Vocabulary (Version 1)

Purpose: Canonical (Phase 2 gated) list of 40K unit / kit names for normalization when both game_system=warhammer_40k and codex_faction resolved and feature flag enable_unit_extraction=true.

Activation Rules:
1. Only evaluate after faction resolution.
2. Low-specificity single tokens ("tactical", "warrior", "captain") require contextual reinforcement (same path contains another unit/faction token) else residual.
3. Generic modifiers (assault, heavy, prime, veteran) refine base unit when paired.

Structure:
```
codex_units:
	warhammer_40k:
		<faction>:
			<canonical_unit_key>: [aliases...]
```

```
codex_units:
	warhammer_40k:
		space_marines:
			intercessor_squad: ["intercessor", "intercessors", "intercessor_squad"]
			assault_intercessor_squad: ["assault_intercessor", "assault_intercessors", "assault_intercessor_squad"]
			heavy_intercessor_squad: ["heavy_intercessor", "heavy_intercessors", "heavy_intercessor_squad"]
			tactical_squad: ["tactical_squad", "tactical_marines", "tactical_marine"]  # bare 'tactical' delayed
			aggressor_squad: ["aggressor", "aggressors", "aggressor_squad"]
			terminator_squad: ["terminator", "terminators", "terminator_squad"]
			bladeguard_veterans: ["bladeguard", "bladeguard_veteran", "bladeguard_veterans"]
			eradicators: ["eradicator", "eradicators"]
			hellblasters: ["hellblaster", "hellblasters"]
			infernus_squad: ["infernus", "infernus_squad"]
			inceptor_squad: ["inceptor", "inceptors", "inceptor_squad"]
			sternguard_veterans: ["sternguard", "sternguard_veteran", "sternguard_veterans"]
			desolation_squad: ["desolation", "desolator", "desolators", "desolation_squad"]
			devastator_squad: ["devastator", "devastators", "devastator_squad"]
			assault_squad: ["assault_squad", "assault_marines"]
			vanguard_veterans: ["vanguard_veteran", "vanguard_veterans", "vanguard"]
			captain: ["captain", "chapter_master"]
			librarian: ["librarian"]
		chapters_generic:
			dreadnought: ["dreadnought", "dread"]
			redemptor_dreadnought: ["redemptor"]
			invictor_warsuit: ["invictor"]
			gladiator_tank: ["gladiator", "gladiator_lancer", "gladiator_reaper", "gladiator_valiant"]
			land_raider: ["land_raider"]
			rhino: ["rhino"]
			impulsor: ["impulsor"]
			storm_speeder: ["storm_speeder", "storm_speeder_hailstrike", "storm_speeder_thunderstrike", "storm_speeder_hammerstrike"]
		necrons:
			warriors: ["necron_warrior", "necron_warriors", "warrior", "warriors"]
			immortals: ["immortal", "immortals"]
			lichguard: ["lichguard"]
			deathmarks: ["deathmark", "deathmarks"]
			destroyers: ["destroyer", "destroyers", "lokhust_destroyer", "lokhust_destroyers"]
			heavy_destroyers: ["heavy_destroyer", "heavy_destroyers", "lokhust_heavy_destroyer", "lokhust_heavy_destroyers"]
			skorpekh_destroyers: ["skorpekh", "skorpekh_destroyer", "skorpekh_destroyers"]
			ophydian_destroyers: ["ophydian", "ophydian_destroyer", "ophydian_destroyers"]
			flayed_ones: ["flayed_one", "flayed_ones"]
			triarch_praetorians: ["triarch_praetorian", "triarch_praetorians", "praetorian", "praetorians"]
			tomb_blades: ["tomb_blade", "tomb_blades"]
			scarab_swarms: ["scarab", "scarabs", "scarab_swarm", "scarab_swarms"]
			canoptek_wraiths: ["wraith", "wraiths", "canoptek_wraith", "canoptek_wraiths"]
			canoptek_scarabs: ["canoptek_scarab", "canoptek_scarabs"]
			monolith: ["monolith"]
			ghost_ark: ["ghost_ark"]
			doomsday_ark: ["doomsday_ark"]
			annihilation_barge: ["annihilation_barge"]
			night_scythe: ["night_scythe"]
			doom_scythe: ["doom_scythe"]
		tyranids:
			termagants: ["termagant", "termagants"]
			hormagaunts: ["hormagaunt", "hormagaunts"]
			gaunts: ["gaunt", "gaunts"]
			genestealers: ["genestealer", "genestealers"]
			broodlord: ["broodlord"]
			warriors: ["tyranid_warrior", "tyranid_warriors", "warrior", "warriors"]
			carnifex: ["carnifex", "carnifexes", "carnifexs"]
			hive_tyrant: ["hive_tyrant", "hive_tyrants", "tyrant"]
			trygon: ["trygon", "trygons"]
			lictor: ["lictor", "lictors"]
			zoanthropes: ["zoanthrope", "zoanthropes"]
			neurotyrant: ["neurotyrant"]
			biovore: ["biovore", "biovores"]
			pyrovore: ["pyrovore", "pyrovores"]
			gaunt_rippers: ["ripper", "rippers", "ripper_swarm", "ripper_swarms"]
		orks:
			boyz: ["boy", "boyz", "ork_boy", "ork_boyz"]
			nobz: ["nob", "nobz"]
			gretchin: ["gretchin", "grot", "grots"]
			warboss: ["warboss"]
			kommando: ["kommando", "kommandos"]
			stormboyz: ["stormboy", "stormboyz"]
			lootas: ["loota", "lootas"]
			burna_boyz: ["burna", "burna_boy", "burna_boyz"]
			mek: ["mek", "big_mek"]
			deff_dread: ["deff_dread"]
			killa_kan: ["killa_kan", "killa_kans"]
			dakkajet: ["dakkajet"]
			battlewagon: ["battlewagon"]
			trukk: ["trukk", "trukks"]
		astra_militarum:
			guardsmen: ["guardsman", "guardsmen", "infantry_squad"]
			cadian_shock_troops: ["cadian", "cadians", "cadian_shock_troops"]
			command_squad: ["command_squad", "command"]
			kasrkin: ["kasrkin"]
			conscripts: ["conscript", "conscripts"]
			ogryn: ["ogryn", "ogryns"]
			ratlings: ["ratling", "ratlings"]
			bullgryn: ["bullgryn", "bullgryns", "bullgrynz"]
			chimera: ["chimera"]
			leman_russ: ["leman_russ", "leman_russ_tank", "leman_russ_battle_tank"]
			baneblade: ["baneblade"]
			sentinel: ["sentinel", "sentinels"]
			basilisk: ["basilisk"]
		adeptus_mechanicus:
			skitarrii_rangers: ["ranger", "rangers", "skitarii_ranger", "skitarii_rangers"]
			skitarrii_vanguard: ["vanguard", "skitarii_vanguard"]
			kataphron_destroyers: ["kataphron_destroyer", "kataphron_destroyers"]
			kataphron_breachers: ["kataphron_breacher", "kataphron_breachers"]
			kastelan_robots: ["kastelan", "kastelan_robot", "kastelan_robots"]
			ironstrider: ["ironstrider", "ironstrider_ballistarius", "sydonian_dragoon"]
			pteraxii: ["pteraxii", "pteraxii_skystalkers", "pteraxii_sterilizers"]
			serberys: ["serberys", "serberys_raiders", "serberys_sulphurhounds"]
			techpriest: ["techpriest", "tech_priest"]
		chaos_space_marines:
			cultists: ["cultist", "cultists"]
			chaos_marines: ["chaos_space_marine", "chaos_space_marines", "csm"]
			chosen: ["chosen"]
			terminators: ["chaos_terminator", "chaos_terminators"]
			possessed: ["possessed"]
			havocs: ["havoc", "havocs"]
			obliterators: ["obliterator", "obliterators"]
			raptors: ["raptor", "raptors"]
			bikers: ["biker", "bikers", "bike", "bikes"]
			venomcrawler: ["venomcrawler"]
			heldrake: ["heldrake"]
			decimator: ["decimator"]
```

TODO: Add remaining factions (Drukhari, Aeldari, T'au, Genestealer Cults, Adepta Sororitas, Custodes, Grey Knights, Imperial/Chaos Knights, Leagues of Votann, Chaos Daemons, Inquisition).
