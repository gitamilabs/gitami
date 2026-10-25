from pathlib import Path
from src.parsing.parser import CodeParser

DISCORD_BOT_DIR = Path(__file__).parent.parent.parent / ".system_generated" if False else Path("/home/aryanracha/.gemini/antigravity-cli/brain/2f078056-09b0-49e7-b707-adf97ab2653f/scratch/discord_bot")


def test_enhanced_python_extractor_discord_bot():
    parser = CodeParser()
    main_file = DISCORD_BOT_DIR / "main.py"
    test_file = DISCORD_BOT_DIR / "test.py"

    main_res = parser.parse_file(main_file, relative_to_dir=DISCORD_BOT_DIR)
    test_res = parser.parse_file(test_file, relative_to_dir=DISCORD_BOT_DIR)

    assert main_res is not None
    assert test_res is not None

    all_symbols = {s.name: s for s in (main_res.symbols + test_res.symbols)}

    # 1. Verify module-level variables, routers, and constants extracted
    assert "app" in all_symbols
    assert all_symbols["app"].kind == "router"

    assert "bot" in all_symbols
    assert all_symbols["bot"].kind == "variable"

    assert "supabase" in all_symbols
    assert all_symbols["supabase"].kind == "variable"

    assert "TOKEN" in all_symbols
    assert all_symbols["TOKEN"].kind == "constant"

    assert "PLATFORM_IDS" in all_symbols
    assert all_symbols["PLATFORM_IDS"].kind == "constant"

    # 2. Verify decorated functions have decorators in signature
    home_sym = all_symbols["home"]
    assert "@app.route('/')" in home_sym.signature
    assert home_sym.kind == "router"

    on_ready_sym = all_symbols["on_ready"]
    assert "@bot.event" in on_ready_sym.signature

    send_link_sym = all_symbols["send_link"]
    assert "@tasks.loop(minutes=1)" in send_link_sym.signature

    # 3. Verify clean aliased imports
    main_imports = {i.imported_symbol: i for i in main_res.imports}
    assert "pytime" not in main_imports  # Shouldn't be raw "time as pytime"
    assert "time" in main_imports
    assert "fetch_contests" in main_imports
    assert "fetch_upcoming_contests" in main_imports

    # 4. Verify higher-order calls and attribute targets
    main_callees = {c.callee_name for c in main_res.calls}
    # check_reminders.start() extracted base obj
    assert "check_reminders" in main_callees
    # Thread(target=run_web) extracted target
    assert "run_web" in main_callees
    # loop.run_in_executor(None, fetch_contests) extracted callable arg
    assert "fetch_contests" in main_callees
    assert "fetch_upcoming_contests" in main_callees

    # 5. Verify inter-file call linkage exists
    inter_calls = [
        c for c in main_res.calls
        if c.callee_name in all_symbols and all_symbols[c.callee_name].file_path == "test.py"
    ]
    assert len(inter_calls) >= 2
    callee_targets = {c.callee_name for c in inter_calls}
    assert "fetch_contests" in callee_targets
    assert "fetch_upcoming_contests" in callee_targets
