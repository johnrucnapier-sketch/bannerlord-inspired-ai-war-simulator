# 本地地图包

第三模式代码公开，真实游戏地图数据不随仓库分发。请使用已经导出的、你有权使用的本地战略地图包；安装目录或DLL不能直接传给本导入器。不要把导入后的JSON、底图、原始场景或游戏存档提交到Git。

需要三份UTF-8 JSON：

- `navigation.json`：`vertices_xy`为原始XY二维数组；`faces`每面含整数id、顶点索引vertices、布尔walkable、相邻面ID列表neighbors。可选category为land/water/mountain/blocked用于渲染，source_group为原地形编号、bridge_overlay标记桥面用于检查。相邻可通行面须共享一条边且双向关联；水下与桥面不可因二维重叠错误连接。
- `settlements.json`：数组，字段id、name、kind(city/village)、original_kind(town/castle/village)、kingdom(empire_w/empire)、x/y图标位置、gate_x/gate_y可通行入口。大型定居点另含owner_clan，村庄另含parent_city。坐标不做归一化。
- `clans.json`：数组，字段id、name、kingdom、initial_home_settlement；可附owned_city_ids。每个国家9家族，每家族3个部队名额由规则决定。

导入器校验西帝国14据点31村、北帝国15据点32村，两国各6城镇；验证所有入口在陆地上、村庄可达其绑定据点、家族归属和导航共享边。它校验结构与可运行性，不证明来源授权，也不能单凭计数证明地理真实性。

```sh
python tools/import_map.py --source /path/to/export --check-only
python tools/import_map.py --source /path/to/export --render
```

`--render`需Pillow，生成本地观察底图；无界面训练无需图片。导入数据进入aiwar/data/west_north，已加入gitignore。已安装的不同哈希地图不会被覆盖；需要更换时用另一份工作目录，或用AIWAR_MAP_DIR指向另一包并重启进程。运行中更改地图文件不受支持。

正式记录三份原始文件字节SHA-256，而不仅是navmesh哈希。JSON空格或排序变化也会改变身份。真实坐标数据的一致性由数据版本及来源核验负责；本仓库的tools/make_test_map.py只生成明确标注的原创CI矩形地图，不能冒充真实地图。
