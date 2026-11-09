# Run: godot --headless --path godot --script ../scripts/check_multinational_viewer.gd
extends SceneTree

func _initialize():
	call_deferred("check_viewer")

func check_viewer():
	var viewer = load("res://main.gd").new()
	root.add_child(viewer)
	var nations = {}
	var totals = []
	for n in range(8):
		nations[str(n)] = {"id":n,"name":"国家%d" % n}
		totals.append({"nation":n,"population":10000,"military":5000,"healthy":4800,"wounded":200})
	viewer.world = {"mode":"realmap","nations":nations,"styles":["march","march","march","march","march","march","march","march"],"strategy_catalog":[{"id":"march","label":"March"}],"observer_totals":totals}
	viewer.update_strategy_choices(viewer.world["styles"])
	assert(viewer.vision_radius("levy") == 6000)
	assert(viewer.vision_radius("patrol") == 8000)
	viewer.world["run_settings"] = {"vision":{"levy":1200}}
	assert(viewer.vision_radius("levy") == 1200)
	assert(viewer.view_choice.item_count == 9)
	assert(viewer.nation_choice.item_count == 8)
	for n in range(8):
		viewer.nation_choice.select(n)
		viewer.update_strategy_choices(viewer.world["styles"])
		assert(viewer.nation_choice.get_selected_id() == n)
		assert(viewer.strategy_choice.selected == 0)
		viewer.view_choice.item_selected.emit(n+1)
		assert(viewer.view == n)
	viewer.queue_redraw()
	await process_frame
	await process_frame
	viewer.world = {"mode":"rural","styles":["march","manual"],"strategy_catalog":[{"id":"march","label":"March"}]}
	viewer.update_strategy_choices(viewer.world["styles"])
	assert(viewer.view == null)
	assert(viewer.nation_choice.item_count == 1)
	assert(viewer.view_choice.item_count == 2)
	viewer.world = {"mode":"duel","styles":["march","march"],"strategy_catalog":[{"id":"march","label":"March"}]}
	viewer.update_strategy_choices(viewer.world["styles"])
	assert(viewer.nation_choice.item_count == 2)
	assert(viewer.view_choice.item_count == 3)
	print("PASS: 8 nation strategies/views, observer reset, rural and duel transitions")
	quit()
