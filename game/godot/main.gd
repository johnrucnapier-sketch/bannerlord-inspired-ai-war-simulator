extends Node2D

const BLUE = Color("62b7f5")
const RED = Color("ef817a")
const MUTED = Color("8faba8")
const INK = Color("dcebe4")
const GOLD = Color("ddbd78")
const MAP = Rect2(202, 170, 1056, 704)
var socket = WebSocketPeer.new()
var world: Dictionary = {}
var selected: String = ""
var view: Variant = null
var font = SystemFont.new()
var status: String = "正在连接本机 Python 核心…"
var retry_at: float = 0
var seen_state: bool = false
var viewer_registered = false
var heartbeat_at = 0
var territory_signature = ""
var territory_texture: ImageTexture
var run_button: Button
var detail: RichTextLabel
var log_box: RichTextLabel
var seed_box: SpinBox
var speed_choice: OptionButton
var blue_choice: OptionButton
var red_choice: OptionButton
var view_choice: OptionButton
var mode_choice: OptionButton
var transport_toggle: CheckButton
var follow_toggle: CheckButton
var last_run: String = ""
var log_signature: String = ""
var army_cache: Array = []
var requested_screenshot: String = ""
var smoke: bool = false
var smoke_started: bool = false
var previous_positions: Dictionary = {}
var received_at: float = 0
var last_hour: int = -1

func _ready():
	font.font_names = PackedStringArray(["PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC"])
	RenderingServer.set_default_clear_color(Color("101d24"))
	var args = OS.get_cmdline_user_args()
	for i in range(args.size()):
		if args[i] == "--smoke": smoke = true
		if args[i] == "--screenshot" and i + 1 < args.size(): requested_screenshot = args[i + 1]
	var usable = DisplayServer.screen_get_usable_rect().size
	var scale_ = maxf(0.4, minf(1.0, minf(float(usable.x - 40) / 1760.0, float(usable.y - 60) / 960.0)))
	get_window().size = Vector2i(Vector2(1760, 960) * scale_)
	make_ui()
	connect_core()

func button_at(caption: String, x: float, y: float, width: float, action: Callable) -> Button:
	var b = Button.new()
	b.text = caption
	b.position = Vector2(x, y)
	b.size = Vector2(width, 34)
	b.add_theme_font_override("font", font)
	b.add_theme_font_size_override("font_size", 15)
	var style = StyleBoxFlat.new()
	style.bg_color = Color("263b44")
	style.corner_radius_top_left = 5
	style.corner_radius_top_right = 5
	style.corner_radius_bottom_left = 5
	style.corner_radius_bottom_right = 5
	b.add_theme_stylebox_override("normal", style)
	b.pressed.connect(action)
	add_child(b)
	return b

func option_at(items: Array, x: float, width: float, action: Callable) -> OptionButton:
	var o = OptionButton.new()
	o.position = Vector2(x, 96)
	o.size = Vector2(width, 34)
	o.add_theme_font_override("font", font)
	o.add_theme_font_size_override("font_size", 15)
	for item in items: o.add_item(item)
	o.item_selected.connect(action)
	add_child(o)
	return o

func make_ui():
	mode_choice = option_at(["1v1对抗模式", "单国护农挑战 · 十年"], 970, 290, func(i): send({"type":"reset", "mode":"duel" if i == 0 else "rural"}))
	mode_choice.position.y = 10
	run_button = button_at("▶ 开始", 20, 96, 90, func(): send({"type":"pause", "value":not world.get("paused",true)}))
	button_at("+1小时", 118, 96, 82, func(): send({"type":"step"}))
	speed_choice = option_at(["1小时 / 秒", "6小时 / 秒", "24小时 / 秒", "120小时 / 秒", "600小时 / 秒", "2400小时 / 秒"], 208, 156,
		func(i): send({"type":"speed", "value":[1,6,24,120,600,2400][i]}))
	speed_choice.select(2)
	view_choice = option_at(["全知观察", "蓝国视角", "赤国视角"], 374, 126, func(i):
		view = null if i == 0 else i - 1
		send({"type":"view", "nation":view}))
	blue_choice = option_at(["蓝：测试进军", "蓝：测试巡逻", "蓝：静置对照", "P1 驻点守护", "P2 随车护送", "P3 环线巡防", "P4 就近救援", "P5 分区协巡", "进军＋P5护农", "W1 保底集中", "W2 风险抽调", "W3 轮换出征", "W4 战区预备"], 510, 152,
		func(i): send({"type":"style", "nation":0, "style":["march","guard","manual","p1","p2","p3","p4","p5","march_p5","w1","w2","w3","w4"][i]}))
	red_choice = option_at(["赤：测试进军", "赤：测试巡逻", "赤：静置对照", "P1 驻点守护", "P2 随车护送", "P3 环线巡防", "P4 就近救援", "P5 分区协巡", "进军＋P5护农", "W1 保底集中", "W2 风险抽调", "W3 轮换出征", "W4 战区预备"], 672, 152,
		func(i): send({"type":"style", "nation":1, "style":["march","guard","manual","p1","p2","p3","p4","p5","march_p5","w1","w2","w3","w4"][i]}))
	button_at("保存", 834, 96, 58, func(): send({"type":"save"}))
	button_at("读取", 900, 96, 58, func(): send({"type":"load"}))
	button_at("重放", 966, 96, 58, func(): send({"type":"replay"}))
	button_at("新局 · 随机", 1032, 96, 106, func(): send({"type":"reset"}))
	seed_box = SpinBox.new()
	seed_box.position = Vector2(1150,96)
	seed_box.size = Vector2(164,34)
	seed_box.min_value = 1
	seed_box.max_value = 2147483647
	seed_box.step = 1
	seed_box.value = 1
	seed_box.add_theme_font_override("font",font)
	seed_box.add_theme_font_size_override("font_size",14)
	add_child(seed_box)
	button_at("按此种子重开",1322,96,130,func(): send({"type":"reset","seed":int(seed_box.value)}))
	detail = RichTextLabel.new()
	detail.position = Vector2(202,895)
	detail.size = Vector2(1056,56)
	detail.add_theme_font_override("normal_font",font)
	detail.add_theme_font_size_override("normal_font_size",14)
	detail.add_theme_color_override("default_color",INK)
	detail.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(detail)
	log_box = RichTextLabel.new()
	log_box.position = Vector2(1280,390)
	log_box.size = Vector2(456,540)
	log_box.bbcode_enabled = true
	log_box.scroll_active = true
	log_box.scroll_following = true
	log_box.add_theme_font_override("normal_font",font)
	log_box.add_theme_font_override("bold_font",font)
	log_box.add_theme_font_size_override("normal_font_size",15)
	log_box.add_theme_color_override("default_color",INK)
	add_child(log_box)
	follow_toggle = CheckButton.new()
	follow_toggle.text = "跟随最新"
	follow_toggle.position = Vector2(1390,345)
	follow_toggle.size = Vector2(135,32)
	follow_toggle.button_pressed = true
	follow_toggle.add_theme_font_override("font",font)
	follow_toggle.add_theme_font_size_override("font_size",14)
	follow_toggle.toggled.connect(func(on): log_box.scroll_following = on)
	add_child(follow_toggle)
	transport_toggle = CheckButton.new()
	transport_toggle.text = "含运输损失"
	transport_toggle.position = Vector2(1550,345)
	transport_toggle.size = Vector2(175,32)
	transport_toggle.add_theme_font_override("font",font)
	transport_toggle.add_theme_font_size_override("font_size",14)
	transport_toggle.toggled.connect(func(_on): log_signature = ""; update_log())
	add_child(transport_toggle)

func update_log():
	var events = world.get("observer_events",[])
	var signature = str(world.get("run_id","")) + ":" + str(events[-1].get("id",0) if events.size() > 0 else 0) + ":" + str(transport_toggle.button_pressed)
	if signature == log_signature: return
	log_signature = signature
	var saved_scroll = log_box.get_v_scroll_bar().value
	var lines = PackedStringArray()
	for e in events:
		if e.get("kind") == "bandit_spawn": continue
		if e.get("kind") == "transport_lost" and not transport_toggle.button_pressed: continue
		var h = int(e["hour"])
		var n = e.get("nation")
		var color = color_for(n).to_html(false) if n != null else INK.to_html(false)
		var message = str(e["text"]).replace("[","[lb]")
		lines.append("[color=#8faba8]第%d年 · 第%02d日 · %02d时[/color]\n[color=#%s]%s[/color]" % [h/2016+1,h/24%84+1,h%24,color,message])
	log_box.text = "\n\n".join(lines) if lines.size() > 0 else "尚无战事。\n\n军队覆灭、城池易主、军团集结等实际事件会显示在这里。"
	if not follow_toggle.button_pressed: log_box.get_v_scroll_bar().set_deferred("value",saved_scroll)

func collect_armies():
	var groups: Dictionary = {}
	for u in world.get("units",[]):
		var aid = u.get("army")
		if aid == null: continue
		if not groups.has(aid):
			groups[aid] = {"id":aid,"name":("蓝国" if u["nation"] == 0 else "赤国") + "军团 " + str(aid),"kind":"army","nation":u["nation"],"x":u["x"],"y":u["y"],"healthy":0,"wounded":0,"members":0,"battle":u.get("battle"),"path":u.get("path",[])}
		groups[aid]["healthy"] += int(u["healthy"])
		groups[aid]["wounded"] += int(u["wounded"])
		groups[aid]["members"] += 1
	army_cache = groups.values()

func army_flag(p: Vector2, color: Color, scale_: float = 1.0):
	draw_circle(p,13*scale_,Color("13272f"))
	draw_arc(p,14*scale_,0,TAU,40,color,2.5*scale_)
	draw_line(p+Vector2(-3,9)*scale_,p+Vector2(-3,-31)*scale_,GOLD,2.5*scale_)
	draw_colored_polygon(PackedVector2Array([p+Vector2(-3,-31)*scale_,p+Vector2(21,-31)*scale_,p+Vector2(15,-21)*scale_,p+Vector2(-3,-21)*scale_]),color)

func draw_sidebars():
	draw_rect(Rect2(20,170,164,760),Color("182d34"))
	text_at("图例",Vector2(34,198),18,GOLD)
	draw_rect(Rect2(35,219,12,12),BLUE);text_at("城市",Vector2(60,230),14)
	draw_circle(Vector2(41,255),3.5,BLUE);text_at("村庄",Vector2(60,260),14)
	draw_circle(Vector2(41,285),5.5,BLUE);text_at("独立部队",Vector2(60,290),14)
	draw_rect(Rect2(37,311,8,8),BLUE);text_at("运输队",Vector2(60,320),14)
	draw_colored_polygon(PackedVector2Array([Vector2(41,341),Vector2(47,352),Vector2(35,352)]),GOLD);text_at("劫匪",Vector2(60,351),14)
	army_flag(Vector2(41,395),BLUE,0.65);text_at("已集结军团",Vector2(60,397),14)
	draw_line(Vector2(34,420),Vector2(170,420),Color("304750"))
	var tips = ["观察操作", "左键查看对象", "再次点击切换重叠", "新局：随机种子", "同种子可复现结果", "", "简要规则", "粮食 / 兵源实际运输", "缺粮每天减员10%", "运输遇袭约5小时", "驻村运输队免遭匪袭", "攻城：逐城向前推进", "救援需实际抵达", "", "统计口径", "人口：村庄＋运输农民", "兵力：驻军＋领主部队", "＋民兵、运粮兵与伤兵", "军团成员不重复计数", "", "统计 / 日志仅供观察", "不会额外提供给AI"]
	for i in range(tips.size()):
		text_at(tips[i],Vector2(34,447+i*22),12,GOLD if i in [0,6,12] else MUTED)
	text_at("国家概况 · 观察者统计",Vector2(1280,151),15,GOLD)
	for t in world.get("observer_totals",[]):
		var x = 1280 + int(t["nation"])*236
		var color = color_for(t["nation"])
		draw_rect(Rect2(x,170,220,159),Color("1c3039"))
		text_at("蓝国" if t["nation"] == 0 else "赤国",Vector2(x+12,194),17,color)
		text_at("人口  %d" % int(t["population"]),Vector2(x+12,222),23,INK)
		text_at("村庄 %d + 运输 %d" % [t["village_population"],t["transport_population"]],Vector2(x+12,243),12,MUTED)
		text_at("总兵力  %d" % int(t["military"]),Vector2(x+12,271),23,INK)
		text_at("可战 %d  /  伤兵 %d" % [t["healthy"],t["wounded"]],Vector2(x+12,293),13,color)
		text_at("驻%d · 野%d · 民%d · 运%d" % [t["garrison"],t["field"],t.get("militia",0),t["logistics"]],Vector2(x+12,315),12,MUTED)
		text_at("领主部队 %d 支 · 军团 %d 个" % [t.get("parties",0),t.get("armies",0)],Vector2(x+12,345),12,color)
	if world.get("mode", "duel") == "rural":
		var score = world.get("rural_score", {})
		text_at("单国护农 · 十年结算",Vector2(1528,194),16,GOLD)
		text_at("人口净增 %d" % score.get("population_gain",0),Vector2(1528,226),17)
		text_at("人口保全 %.2f%%" % (score.get("population_retention",1)*100),Vector2(1528,256),16)
		text_at("无损人口 %d" % score.get("no_loss_population",0),Vector2(1528,284),14)
		text_at("遭劫运输队 %d" % score.get("bandit_cart_losses",0),Vector2(1528,312),14)
	text_at("战况日志",Vector2(1280,370),19,GOLD)
	draw_line(Vector2(1270,170),Vector2(1270,930),Color("304750"))
	text_at("可滚动回看；取消“跟随最新”可停留阅读",Vector2(1280,952),12,MUTED)

func connect_core():
	socket = WebSocketPeer.new()
	# Full world snapshots grow beyond the default 64 KiB as logs accumulate.
	socket.inbound_buffer_size = 8 * 1024 * 1024
	seen_state = false
	viewer_registered = false
	var error = socket.connect_to_url("ws://127.0.0.1:18765")
	if error != OK: status = "核心尚未启动，自动重连中…"
	retry_at = Time.get_ticks_msec() / 1000.0 + 3.0

func send(payload: Dictionary):
	if socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
		socket.send_text(JSON.stringify(payload))
	else: status = "未连接：请先运行启动脚本"

func _process(_delta):
	socket.poll()
	if socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
		if not viewer_registered:
			send({"type":"viewer"})
			viewer_registered = true
		while socket.get_available_packet_count() > 0:
			var packet = JSON.parse_string(socket.get_packet().get_string_from_utf8())
			if not packet is Dictionary: continue
			if packet.get("type") == "state":
				if Time.get_ticks_msec() >= heartbeat_at:
					send({"type":"heartbeat"})
					heartbeat_at = Time.get_ticks_msec() + 1000
				var next: Dictionary = packet["data"]
				if int(next.get("hour",0)) != last_hour:
					previous_positions.clear()
					for u in world.get("units",[]): previous_positions[u["id"]] = point(u)
					received_at = Time.get_ticks_msec()/1000.0
					last_hour = int(next.get("hour",0))
				world = next
				update_territory()
				collect_armies()
				if str(world.get("run_id","")) != last_run:
					last_run = str(world.get("run_id",""))
					seed_box.value = int(world.get("seed",1))
					selected = ""
					log_signature = ""
				var rural = world.get("mode", "duel") == "rural"
				mode_choice.select(1 if rural else 0)
				red_choice.visible = not rural
				if rural and view == 1:
					view = null
					view_choice.select(0)
					send({"type":"view", "nation":null})
				view_choice.set_item_disabled(2, rural)
				var styles = world.get("styles",["march","march"])
				blue_choice.select(["march","guard","manual","p1","p2","p3","p4","p5","march_p5","w1","w2","w3","w4"].find(styles[0]))
				red_choice.select(["march","guard","manual","p1","p2","p3","p4","p5","march_p5","w1","w2","w3","w4"].find(styles[1]))
				var speed_index = [1,6,24,120,600,2400].find(int(world.get("speed",24)))
				if speed_index >= 0: speed_choice.select(speed_index)
				update_log()
				if not seen_state: status = "已连接 · 观察模式 · 左键查看城市、村庄与队伍"
				seen_state = true
				if world.get("paused",true) and world.get("pause_reason","") != "": status = world["pause_reason"]
				run_button.text = "▶ 继续" if world.get("paused",true) else "Ⅱ 暂停"
				update_detail()
				if smoke and not smoke_started:
					smoke_started = true
					smoke_test()
			elif packet.get("type") == "ack":
				status = "操作完成：" + str(packet.get("action","命令")) if packet.get("ok") else "未执行：" + str(packet.get("error","未知错误"))
	elif socket.get_ready_state() == WebSocketPeer.STATE_CLOSED and Time.get_ticks_msec()/1000.0 > retry_at:
		print("AIWAR_SOCKET_CLOSED code=", socket.get_close_code(), " reason=", socket.get_close_reason())
		status = "本机核心连接断开，正在重连…"
		connect_core()
	queue_redraw()

func smoke_test():
	send({"type":"step"})
	await get_tree().create_timer(1.0).timeout
	print("AIWAR_GODOT_SMOKE hour=",world.get("hour")," cities=",world.get("cities",[]).size())
	if requested_screenshot != "":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(requested_screenshot)
	get_tree().quit(0 if int(world.get("hour",0)) > 0 and world.get("cities",[]).size() == 12 else 1)

func point(o: Dictionary) -> Vector2:
	return MAP.position + Vector2(float(o["x"])/120000.0*MAP.size.x,float(o["y"])/80000.0*MAP.size.y)

func color_for(n) -> Color:
	return BLUE if n == 0 else RED if n == 1 else GOLD

func text_at(s: String, p: Vector2, size_: int = 16, color: Color = INK):
	draw_string(font,p,s,HORIZONTAL_ALIGNMENT_LEFT,-1,size_,color)

func object_by_id(id: String) -> Dictionary:
	for army in army_cache:
		if army["id"] == id: return army
	for kind in ["units","cities","villages"]:
		for o in world.get(kind,[]):
			if o["id"] == id: return o
	return {}

func nearest_object(p: Vector2, radius: float = 15.0) -> Dictionary:
	var best: Dictionary = {}
	var distance = radius
	for kind in ["units","cities","villages"]:
		for o in world.get(kind,[]):
			if o.get("kind") in ["garrison","militia"]: continue
			var dd = point(o).distance_to(p)
			if dd < distance:
				distance = dd
				best = o
	return best

func _unhandled_input(event):
	if event is InputEventMouseButton and event.pressed and MAP.has_point(event.position):
		var target = nearest_object(event.position)
		if event.button_index == MOUSE_BUTTON_LEFT:
			var candidates = []
			for army in army_cache:
				if point(army).distance_to(event.position) < 24: candidates.append(str(army["id"]))
			for category in ["cities","units","villages"]:
				for item in world.get(category,[]):
					if not item.get("kind") in ["garrison","militia"] and item.get("army") == null and point(item).distance_to(event.position) < 16:
						candidates.append(str(item["id"]))
			if candidates.size() > 0:
				selected = candidates[(candidates.find(selected) + 1) % candidates.size()]
			else: selected = ""
			update_detail()

func update_detail():
	var o = object_by_id(selected)
	if o.is_empty():
		detail.text = "左键查看城市、村庄、部队或军团详情。多支独立部队重叠不等于已集结军团。"
		return
	var lines = [str(o.get("name",o["id"])), "蓝国" if o.get("nation") == 0 else "赤国" if o.get("nation") == 1 else "劫匪"]
	if o.get("stale",false): lines.append("最后观察（非实时）")
	for key in ["kind","population","healthy","wounded","recruits","cargo_recruits","clan","phase","members","refill_target"]:
		if o.has(key):
			if key == "recruits" and o.has("garrison") and int(o[key]) == 0: continue
			var names = {"kind":"类型","population":"人口","healthy":"健康","wounded":"伤兵","recruits":"兵源","cargo_recruits":"载运兵源","clan":"家族","phase":"状态","members":"军团部队数","refill_target":"整补目标"}
			var value = str(o[key])
			if key in ["population","healthy","wounded","recruits","cargo_recruits","clan","members"]: value = str(int(o[key]))
			if key == "kind": value = {"party":"领主部队","garrison":"驻军","militia":"民兵","village_cart":"村庄运输队","city_cart":"城市运粮队","bandit":"劫匪","army":"军团"}.get(value,value)
			lines.append(str(names[key])+"："+value)
	for key in ["food","cargo_food"]:
		if o.has(key): lines.append(("粮食：" if key == "food" else "货粮：")+"%.2f" % (float(o[key])/1000))
	if o.has("garrison"):
		var g = object_by_id(o["garrison"])
		if not g.is_empty(): lines.append("驻军：%d / 伤兵 %d" % [g["healthy"],g["wounded"]])
	if o.has("clan") and (view == null or o.get("nation") == view):
		var clan_parties = world.get("units",[]).filter(func(u): return u.get("kind") == "party" and u.get("clan") == o["clan"])
		lines.append("本家族领主部队：%d支" % clan_parties.size())
	if o.has("militia"):
		var m = object_by_id(o["militia"])
		if not m.is_empty(): lines.append("民兵：%d / 伤兵 %d / 上限200" % [m["healthy"],m["wounded"]])
	if o.has("militia_healthy"): lines.append("已知民兵：%d / 伤兵 %d" % [o["militia_healthy"],o.get("militia_wounded",0)])
	var own_order = o.get("order",{})
	if own_order == null: own_order = {}
	if own_order.get("relief_action") == "wait": lines.append("城外会合/等待战机")
	elif own_order.get("relief_action") == "attack": lines.append("协同解围出击")
	if o.get("battle") != null: lines.append("交战中")
	if o.has("disabled_until") and o["disabled_until"] > world.get("hour",0): lines.append("停产剩余 %d 小时" % (o["disabled_until"]-world["hour"]))
	if o.get("kind") == "bandit":
		var order = o.get("order", {})
		if order == null: order = {}
		var behavior = {"flee":"躲避追兵", "attack":"追击运输队", "roam":"游荡"}
		lines.append("行为：" + str(behavior.get(order.get("type",""),"等待")))
	if o.has("city") and not o.has("kind"):
		var city = object_by_id(o["city"])
		if not city.is_empty(): lines.append("距所属城：%.1f" % (Vector2(o["x"],o["y"]).distance_to(Vector2(city["x"],city["y"]))/1000.0))
	detail.text = "  |  ".join(lines)

func update_territory():
	# Use only the cities supplied by this observation (including last known ownership).
	var cities = world.get("cities",[])
	var signature = JSON.stringify(cities.map(func(c): return [c["id"],c["nation"],c["x"],c["y"]]))
	if signature == territory_signature: return
	territory_signature = signature
	var img = Image.create(264,176,false,Image.FORMAT_RGBA8)
	for y in range(176):
		for x in range(264):
			var pos = Vector2((x+0.5)*120000.0/264.0,(y+0.5)*80000.0/176.0)
			var blue = 0.0
			var red = 0.0
			for c in cities:
				# Smooth inverse-distance influence: near a city its own country dominates.
				var distance_squared = maxf(pos.distance_squared_to(Vector2(c["x"],c["y"])),1.0)
				var influence = 1.0 / (distance_squared * distance_squared)
				if int(c["nation"]) == 0: blue += influence
				elif int(c["nation"]) == 1: red += influence
			var mix_value = smoothstep(0.30,0.70,red/maxf(blue+red,1e-30))
			var tint = BLUE.lerp(RED,mix_value)
			tint.a = 0.14 if blue+red > 0 else 0.0
			img.set_pixel(x,y,tint)
	territory_texture = ImageTexture.create_from_image(img)
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR

func _draw():
	draw_rect(Rect2(0,0,1760,80),Color("162a33"))
	text_at("AI WAR LAB",Vector2(32,33),22,GOLD)
	text_at("战争策略模拟器",Vector2(32,62),18)
	text_at("V0.1.6  /  战况观察",Vector2(280,45),14,MUTED)
	var hour = int(world.get("hour",0))
	text_at("第 %d 年  ·  第 %02d 日  ·  %02d:00" % [hour/2016+1,hour/24%84+1,hour%24],Vector2(640,44),20)
	var war_names = {"w1":"W1保底集中", "w2":"W2风险抽调", "w3":"W3轮换出征", "w4":"W4战区预备", "march":"默认进军", "march_p5":"默认进军＋P5"}
	var active_styles = world.get("styles",[])
	if active_styles.size() == 2 and (active_styles[0] in ["w1","w2","w3","w4"] or active_styles[1] in ["w1","w2","w3","w4"]):
		text_at("蓝：" + war_names.get(active_styles[0],active_styles[0]) + "   赤：" + war_names.get(active_styles[1],active_styles[1]),Vector2(570,73),13,GOLD)
	elif "march_p5" in active_styles:
		text_at("蓝：" + ("P5护农" if world["styles"][0] == "march_p5" else "默认护农") + "   赤：" + ("P5护农" if world["styles"][1] == "march_p5" else "默认护农") + "   双方沿用默认战斗",Vector2(570,73),13,GOLD)
	var counts = [0,0]
	for c in world.get("cities",[]):
		if int(c.get("nation",-1)) in [0,1]: counts[int(c["nation"])]+=1
	text_at("蓝 %d 城" % counts[0],Vector2(1280,32),18,BLUE)
	if world.get("mode", "duel") != "rural":
		text_at("赤 %d 城" % counts[1],Vector2(1516,32),18,RED)
	text_at("领土归属" if view == null else "已知归属",Vector2(1280,59),13,MUTED)
	text_at(status.left(85),Vector2(202,151),13,MUTED)
	text_at("输入种子可复现 · 新局会换种子",Vector2(1470,119),12,MUTED)
	draw_sidebars()
	draw_rect(MAP,Color("263d3b"))
	var terrain = world.get("terrain",[])
	var cell = Vector2(MAP.size.x/60,MAP.size.y/40)
	for y in range(terrain.size()):
		for x in range(terrain[y].size()):
			var value = terrain[y][x]
			if value != 0:
				draw_rect(Rect2(MAP.position+Vector2(x,y)*cell,cell),Color("172a31") if value == 2 else Color("314941"))
	if territory_texture: draw_texture_rect(territory_texture,MAP,false)
	for x in range(0,61,5): draw_line(MAP.position+Vector2(x*cell.x,0),MAP.position+Vector2(x*cell.x,MAP.size.y),Color(0.6,0.8,0.7,0.07))
	for y in range(0,41,5): draw_line(MAP.position+Vector2(0,y*cell.y),MAP.position+Vector2(MAP.size.x,y*cell.y),Color(0.6,0.8,0.7,0.07))
	if view != null:
		# Draw fog cells from the same vision radii; hidden entities are absent at source.
		var sources = []
		for c in world.get("cities",[]):
			if c["nation"] == view and c.has("food"): sources.append([point(c),88.0])
		for v in world.get("villages",[]):
			if v["nation"] == view and v.has("food"): sources.append([point(v),52.8])
		for u in world.get("units",[]):
			if u["nation"] == view:
				sources.append([point(u),70.4 if u["kind"] == "party" else 88.0 if u["kind"] == "garrison" else 35.2])
		for y in range(40):
			for x in range(60):
				var p = MAP.position+(Vector2(x,y)+Vector2(0.5,0.5))*cell
				var visible_ = false
				for src in sources:
					if p.distance_to(src[0]) <= src[1]: visible_ = true; break
				if not visible_: draw_rect(Rect2(MAP.position+Vector2(x,y)*cell,cell),Color(0.02,0.05,0.09,0.6))
	for v in world.get("villages",[]):
		var c = object_by_id(v.get("city",""))
		if not c.is_empty(): draw_line(point(v),point(c),Color(0.7,0.8,0.6,0.14),1)
		var p = point(v)
		draw_circle(p,3.5,color_for(v["nation"]).darkened(0.25))
		if v.get("disabled_until",0)>hour: draw_circle(p,6,Color("ce834c"),false,2)
	for c in world.get("cities",[]):
		var p = point(c)
		var color = color_for(c["nation"])
		if c.get("stale",false): color = color.darkened(0.45)
		draw_circle(p,14,Color("15272e"))
		draw_rect(Rect2(p-Vector2(7,7),Vector2(14,14)),color)
		text_at(c["name"],p+Vector2(-18,-20),14,color)
		var militia = object_by_id(c.get("militia",""))
		if not militia.is_empty(): text_at("民兵 %d" % int(militia["healthy"]),p+Vector2(-23,28),11,MUTED)
		elif c.has("militia_healthy"): text_at("民兵 %d" % int(c["militia_healthy"]),p+Vector2(-23,28),11,MUTED)
	for u in world.get("units",[]):
		if u["kind"] in ["garrison","militia"] or u.get("army") != null: continue
		var p = point(u)
		if previous_positions.has(u["id"]) and not world.get("paused",true) and not u.get("battle"):
			p = previous_positions[u["id"]].lerp(p,clampf((Time.get_ticks_msec()/1000.0-received_at)/0.1,0,1))
		var color = color_for(u["nation"])
		if u["kind"] == "party":
			draw_circle(p,5.5,color)
			text_at(str(int(u["healthy"])),p+Vector2(7,4),11,color)
		elif u["kind"] == "bandit":
			draw_colored_polygon(PackedVector2Array([p+Vector2(0,-5),p+Vector2(5,4),p+Vector2(-5,4)]),GOLD)
		else: draw_rect(Rect2(p-Vector2(3,3),Vector2(6,6)),color)
	for army in army_cache:
		var p = point(army)
		var color = color_for(army["nation"])
		army_flag(p,color)
		var external = world.get("battles",[]).any(func(b): return b.get("id") == army.get("battle") and b.get("kind") == "relief_field")
		var label = "军团 可战%d ·%d队" % [army["healthy"],army["members"]] if external else "军团 %d人 · %d队" % [int(army["healthy"])+int(army["wounded"]),army["members"]]
		var label_width = 165 if external else 145
		var label_x = p.x-label_width-10 if external and int(army["nation"]) == 0 else p.x+22
		var label_pos = Vector2(clampf(label_x,MAP.position.x,MAP.end.x-label_width),maxf(p.y-13,MAP.position.y+25))
		draw_rect(Rect2(label_pos-Vector2(3,17),Vector2(label_width,24)),Color(0.04,0.10,0.13,0.93))
		text_at(label,label_pos,14 if external else 15,color)
	for b in world.get("battles",[]):
		var p = point(b)
		var remaining = int(b["start"])+int(b.get("prepare_hours",24))+int(b.get("paused_hours",0))-hour
		draw_circle(p,13,Color("f3aa64"),false,2)
		if remaining <= 0:
			draw_line(p-Vector2(7,7),p+Vector2(7,7),GOLD,2)
			draw_line(p+Vector2(-7,7),p+Vector2(7,-7),GOLD,2)
		var battle_label = ("围城 · 剩%d小时" % remaining if remaining>0 else "攻城交战") if b.get("kind") == "siege" else "接战准备" if remaining>0 else "运输遇袭" if b.get("kind") == "ambush" else "交战中"
		if b.get("relief_battle") != null: battle_label = "解围野战中 · 攻城暂停"
		if b.get("kind") == "relief_field": battle_label = "解围野战准备" if remaining>0 else "城外解围野战"
		text_at(battle_label,p+Vector2(15,70 if b.get("kind") == "relief_field" else 48),12,GOLD)
	var chosen = object_by_id(selected)
	if not chosen.is_empty():
		draw_arc(point(chosen),18,0,TAU,40,Color.WHITE,1.5)
		var prev = point(chosen)
		for xy in chosen.get("path",[]):
			var p = point({"x":xy[0],"y":xy[1]})
			draw_line(prev,p,Color(1,1,1,0.35),1)
			prev = p
	text_at("对象详情",Vector2(202,889),12,GOLD)
	text_at("种子 %s · 规则%s%s" % [str(int(world.get("seed",1))),str(world.get("rule_version","")),"（旧规则存档）" if world.get("rule_version","") != "0.1.6" else ""],Vector2(856,889),12,MUTED)
	if world.get("result") != null:
		var r = world["result"]
		draw_rect(Rect2(470,400,520,110),Color(0.04,0.09,0.12,0.96))
		var label = "平局" if r.get("winner") == null else "蓝国胜利" if r["winner"] == 0 else "赤国胜利"
		if r.get("reason") == "rural_time_limit": label = "护农完成：人口 %d" % r["score"]["population"]
		text_at(label,Vector2(500,445),28,GOLD)
		text_at("统一完成" if r["reason"] == "unification" else "到达对局时间上限",Vector2(620,479),17)
