import asyncio
from typing import List
from hummingbot.client.command.config_command import ConfigCommand
from hummingbot.core.utils.async_utils import safe_ensure_future
import pandas as pd
from decimal import Decimal


OPTIONS = [
    "bullish",
    "bearish",
    "bullish+",
    "bearish+",
    "set_bull_trap",
    "set_bear_trap",
    "all_in",
    "cautious"
]

playbook = []


class PlayCommand:
    def play(self,
             option: str = None,
             args: List[str] = None
             ):
        self.app.clear_input()
        if option is None:
            safe_ensure_future(self.show_balances())
        else:
            safe_ensure_future(self.play_command(option, args))

    def playbook(self):
        self.app.clear_input()
        rows = []
        for command, status in playbook:
            rows.append({"Play": command, "Status": status})
        df = pd.DataFrame(data=rows, columns=["Play", "Status"])
        first_col_length = max(*df.Play.apply(len))
        df_lines = df.to_string(index=False, formatters={"Play": ("{:<" + str(first_col_length) + "}").format}).split("\n")
        lines = ["    " + line for line in df_lines]
        self._notify("Here is your playbook.")
        self._notify("\n".join(lines))

    async def play_command(self, option: str, args: List[str] = None):
        async def display(msg, delay=0.75):
            await asyncio.sleep(delay)
            self._notify(msg)

        play_status = "activated"
        if option == "bullish":
            await display("Roger that.", 0.25)
            ConfigCommand.update_running_pure_mm(self.strategy, "bid_spread",
                                                 self.strategy_config_map["bid_spread"].value * Decimal("0.75"))
            ConfigCommand.update_running_pure_mm(self.strategy, "ask_spread",
                                                 self.strategy_config_map["ask_spread"].value * Decimal("1.25"))
            await display("bid_spread is shortened by 25% and ask_spread is widen by 25%.")
        elif option == "all_in":
            await display("Right away.")
            ConfigCommand.update_running_pure_mm(self.strategy, "order_amount", Decimal("2"))
            await display("All positions are deployed at maximum capacity.")
        elif option == "set_bull_trap":
            await display("Affirmative.")
            await display(f"A bull trap is set at {args[1]}, when target is apprehended, we'll deploy {args[3]} buy orders.")
            play_status = "in-play"
        command = f"{option} {' '.join(args)}"
        playbook.append((command, play_status))
