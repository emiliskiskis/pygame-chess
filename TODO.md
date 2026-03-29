Known Gaps / Incomplete Features
Issue	Detail
No pawn promotion UI	Auto-promotes to queen; no choice dialog
Board flip broken	flipped variable exists but never set to True
chess.py unused	File exists but nothing imports it
torch/torchvision unused	Listed in pyproject.toml but no import torch anywhere
No undo/redo	Moves can't be taken back
No draw/resign	Only stalemate/checkmate end the game
No PGN export	Move history shown in UI but not exportable
AI is weak	Depth-2 only; no opening book, no endgame tables
No sound	Completely silent