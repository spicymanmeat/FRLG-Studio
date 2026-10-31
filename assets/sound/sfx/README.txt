FRLG Studio PC/UI cue kit
=========================

12 WAV files supply 32 logical cue names. Several features deliberately share
one official sound, so the loader aliases the extra names instead of shipping
duplicate copies. Files are 44.1 kHz mono, rendered from the actual
HeartGold/SoulSilver sound archive (gs_sound_data.sdat) with the kode54 SSEQ
player. They are the retail sequences and SWAV samples, not oscillator
approximations; leading and trailing silence is trimmed and the SSEQ tempo is
preserved.

Shared UI:

  a_button_press  SEQ_SE_DP_SELECT      1500
      aliases: a_button_press, menu_move, ui_click, ui_confirm, ui_close,
               trade_cancel
  menu_select     SEQ_SE_DP_DECIDE      1501
      aliases: menu_select, ui_back, ui_error, ui_warning, pc_deposit,
               pc_withdraw, pc_release, pc_import, pc_undo, pc_error,
               trade_start, trade_failed
  open_settings   SEQ_SE_DP_SELECT78    1504
      aliases: open_settings, link_connected
  ui_toggle       SEQ_SE_DP_BUTTON3     1509
  ui_open         SEQ_SE_DP_OPEN2       1518
      aliases: ui_open, editor_open

Bill's PC:

  pc_open         SEQ_SE_DP_PC_LOGIN    1548
  pc_close        SEQ_SE_DP_PC_LOGOFF   1549
  pc_pick         SEQ_SE_DP_BOX02       1515
      aliases: pc_pick, pc_move
  pc_place        SEQ_SE_DP_BOX01       1514
      aliases: pc_place, pc_swap

Link, trade and editor:

  link_incoming   SEQ_SE_DP_PINPON      1521
  trade_complete  SEQ_SE_DP_KATI        1526
  editor_save     SEQ_SE_DP_SAVE        1562

`menu_select` requests prefer `a_button_press.wav` when it exists, so tabs,
box changes and general menu presses use the short SELECT click. If that file
is absent, `menu_select.wav` (DECIDE) is the fallback. BOX01 and BOX02 are
reserved for the storage hand: a lift uses BOX02; an empty-slot drop, a
same-slot drop or a swap uses one BOX01 set-down. Never play two set-downs for
one move. Entering Bill's PC uses PC_LOGIN; leaving it for any other tab or
the title, or closing the app while the PC is open, uses PC_LOGOFF.

`ui_warning` and `trade_failed` are real call sites; both resolve to
`menu_select` rather than duplicate the DECIDE file. The old `pc_box`,
`pc_cancel`, `pc_cursor` and `ui_tab` names were removed. Box and tab changes
use `menu_select`; deselection uses `pc_place`.

SEQ_SE_DP_BOX03 (1523) is deliberately unused. It was the exclamation refusal
sound and must not return.

The user soundpack at ~/.local/share/frlg-studio/soundpack/sfx/ is read first
and overrides a built-in file with the same name. `menu_select` is the one
exception: it intentionally prefers `a_button_press.wav` while that file
exists. Use SOUND SETTINGS -> RELOAD PACK after changing files. The old oscillator generator in tools/generate_pc_sfx.py is
historical only; do not run it against this folder.
