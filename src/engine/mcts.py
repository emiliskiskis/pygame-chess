"""
mcts.py — Monte Carlo Tree Search for chess.

Shared between train_selfplay.py and the in-game ML vs ML self-play mode.

Public API:
  mcts_search(model, board, turn, last_move, castling_rights,
              num_simulations, c_puct=1.5, device=None, temperature=1.0)
  → (policy_dict, chosen_move, board_tensor)  or  (None, None, None)

  policy_dict:  {move_idx: normalised_visit_count}  (sparse)
  chosen_move:  (fr, fc, tr, tc)
  board_tensor: shape [18, 8, 8]  — the board state BEFORE the chosen move
"""

import copy

import torch

from .board import all_legal_moves, execute_move, is_in_check, opponent
from .ml_model import board_to_tensor, move_to_index


class MCTSNode:
    """A node in the MCTS tree.

    W is accumulated from THIS node's player's perspective.
    High W = good for the player to move here.  Because turns alternate,
    the parent uses -child.Q when selecting among children.
    """

    __slots__ = ["N", "W", "P", "children"]

    def __init__(self, prior=0.0):
        self.N = 0
        self.W = 0.0
        self.P = prior
        self.children = {}  # move_idx -> (MCTSNode, (fr, fc, tr, tc))

    @property
    def Q(self):
        return self.W / self.N if self.N > 0 else 0.0


def _expand_node(node, policy_logits, moves):
    """Populate node.children with prior probabilities from the policy network."""
    mask = torch.full((4096,), float("-inf"))
    for fr, fc, tr, tc in moves:
        mask[move_to_index(fr, fc, tr, tc)] = 0.0
    probs = torch.softmax(policy_logits.squeeze(0) + mask, dim=0)
    for fr, fc, tr, tc in moves:
        idx = move_to_index(fr, fc, tr, tc)
        node.children[idx] = (MCTSNode(prior=probs[idx].item()), (fr, fc, tr, tc))


def mcts_search(
    model,
    board,
    turn,
    last_move,
    castling_rights,
    num_simulations,
    c_puct=1.5,
    device=None,
    temperature=1.0,
):
    """Run MCTS from the current position and return a move with its policy.

    Each simulation:
      1. Selection  — follow PUCT until an unvisited leaf
      2. Expansion  — evaluate leaf with network, populate children with priors
      3. Backup     — propagate value up the path, alternating sign each level

    Returns (policy_dict, chosen_move, board_tensor) or (None, None, None)
    if there are no legal moves in the current position.
    """
    if device is None:
        device = torch.device("cpu")

    moves = all_legal_moves(board, turn, last_move, castling_rights)
    if not moves:
        return None, None, None

    # Capture the board tensor BEFORE simulations mutate the board copies
    board_tensor = board_to_tensor(board, turn, castling_rights, last_move).squeeze(0)

    root = MCTSNode(prior=1.0)

    for _ in range(num_simulations):
        node = root
        path = []

        sim_board = copy.deepcopy(board)
        sim_turn = turn
        sim_last = last_move
        sim_castling = copy.deepcopy(castling_rights)

        # ── Selection ────────────────────────────────────────────────────────
        while node.N > 0 and node.children:
            total_N = node.N
            best_score = -float("inf")
            best_idx = None
            for idx, (child, _) in node.children.items():
                score = -child.Q + c_puct * child.P * (total_N ** 0.5) / (1 + child.N)
                if score > best_score:
                    best_score = score
                    best_idx = idx

            child_node, move = node.children[best_idx]
            path.append(node)
            fr, fc, tr, tc = move
            sim_last, sim_castling, _ = execute_move(
                sim_board, (fr, fc), (tr, tc), sim_last, sim_castling, sim_turn
            )
            sim_turn = opponent(sim_turn)
            node = child_node

        # ── Expansion + Evaluation ───────────────────────────────────────────
        sim_moves = all_legal_moves(sim_board, sim_turn, sim_last, sim_castling)

        if not sim_moves:
            value = -1.0 if is_in_check(sim_board, sim_turn) else 0.0
        else:
            tensor = board_to_tensor(
                sim_board, sim_turn, sim_castling, sim_last
            ).to(device)
            with torch.no_grad():
                policy_logits, v = model(tensor)
            value = v.item()
            _expand_node(node, policy_logits, sim_moves)

        # ── Backup ───────────────────────────────────────────────────────────
        node.W += value
        node.N += 1
        for ancestor in reversed(path):
            value = -value
            ancestor.W += value
            ancestor.N += 1

    # ── Build policy dict from visit counts ──────────────────────────────────
    total_visits = sum(child.N for child, _ in root.children.values())
    policy_dict = {
        idx: child.N / total_visits
        for idx, (child, _) in root.children.items()
        if child.N > 0
    }

    # ── Choose move proportional to visit counts (temperature scaling) ───────
    visit_counts = torch.zeros(4096)
    for idx, (child, _) in root.children.items():
        visit_counts[idx] = child.N
    visit_powered = visit_counts ** (1.0 / max(temperature, 1e-3))
    probs = visit_powered / visit_powered.sum()
    chosen_idx = int(torch.multinomial(probs, 1).item())
    chosen_move = root.children[chosen_idx][1]

    return policy_dict, chosen_move, board_tensor
