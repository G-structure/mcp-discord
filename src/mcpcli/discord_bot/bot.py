import discord
from discord.ext import commands
import json
import os
from typing import List, Dict, Any
from mcpcli.discord_bot.bot_config import BotConfig
from mcpcli.chat_handler import handle_discord_chat
from mcpcli.config import load_config
from mcpcli.transport.stdio.stdio_client import stdio_client
from mcpcli.messages.send_initialize_message import send_initialize

class MCPDiscordBot(commands.Bot):
    def __init__(self, config: BotConfig, server_streams: List[tuple]):
        print("[green]Booting up bot[/green]")
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=config.command_prefix, 
            intents=intents,
            description="MCP Discord Bot"
        )
        self.mcp_config = config
        self.server_streams = server_streams
        self.active_conversations: Dict[int, List[Dict[str, Any]]] = {}
        print("[green]Bot booted now connecting.[/green]")

        
    async def setup_hook(self):
        """Called before the bot starts running."""
        await self.add_cog(ChatCog(self))
        print("[green]Bot is ready to serve![/green]")
        
    async def on_ready(self):
        """Called when the bot has connected to Discord."""
        print(f"[bold green]Logged in as {self.user} (ID: {self.user.id})[/bold green]")
        print("\n[cyan]Connected to servers:[/cyan]")
        for guild in self.guilds:
            print(f"- {guild.name} (ID: {guild.id})")
        print("\n[cyan]Watching channels:[/cyan]")
        for channel_config in self.mcp_config.allowed_channels:
            print(f"- Channel ID: {channel_config.id}")

class ChatCog(commands.Cog):
    def __init__(self, bot: MCPDiscordBot):
        self.bot = bot
        print("[blue]ChatCog initialized[/blue]")
        
    @commands.command(name="chat")
    async def chat(self, ctx: commands.Context, *, message: str):
        print(f"[blue]Received chat command in channel {ctx.channel.id} with message: {message}[/blue]")
        
        # Check if channel is allowed
        channel_allowed = any(
            chan.id == ctx.channel.id for chan in self.bot.mcp_config.allowed_channels
        )
        if not channel_allowed:
            print(f"[red]Channel {ctx.channel.id} is not allowed[/red]")
            return
            
        # Initialize conversation history if needed
        if ctx.channel.id not in self.bot.active_conversations:
            self.bot.active_conversations[ctx.channel.id] = []
            print(f"[blue]Initialized conversation history for channel {ctx.channel.id}[/blue]")
            
        # Add user message to history
        self.bot.active_conversations[ctx.channel.id].append({
            "role": "user",
            "content": message
        })
        print(f"[blue]Added user message to history for channel {ctx.channel.id}[/blue]")
        
        async with ctx.typing():
            print(f"[blue]Handling chat mode for channel {ctx.channel.id}[/blue]")
            response = await handle_discord_chat(
                self.bot.server_streams,
                self.bot.mcp_config.default_provider,
                self.bot.mcp_config.default_model,
                self.bot.active_conversations[ctx.channel.id]
            )
            print(f"[blue]Received response for channel {ctx.channel.id}[/blue]")
            
        if response:
            await ctx.send(response)
            print(f"[blue]Sent response to channel {ctx.channel.id}[/blue]")
        else:
            await ctx.send("Sorry, I couldn't generate a response.")

async def start_bot(config_path: str, server_names: List[str], bot_config_path: str):
    try:
        # Load bot configuration
        with open(bot_config_path) as f:
            bot_config = BotConfig.model_validate(json.load(f))
        
        # Initialize server connections
        server_streams = []
        context_managers = []  # Store context managers to keep them alive
        
        for server_name in server_names:
            server_params = await load_config(config_path, server_name)
            cm = stdio_client(server_params)
            read_stream, write_stream = await cm.__aenter__()
            context_managers.append(cm)  # Keep reference to context manager
            
            init_result = await send_initialize(read_stream, write_stream)
            if init_result:
                server_streams.append((read_stream, write_stream))
                print(f"[green]Successfully connected to server: {server_name}[/green]")
        
        if not server_streams:
            print("[red]No server connections established. Exiting.[/red]")
            # Cleanup context managers
            for cm in context_managers:
                await cm.__aexit__(None, None, None)
            return
        
        # Create and start bot
        print(f"[cyan]Number of active server connections: {len(server_streams)}[/cyan]")
        bot = MCPDiscordBot(bot_config, server_streams)
        print("[green]Starting Discord bot...[/green]")
        
        try:
            # Run the bot
            async with bot:
                await bot.start(bot_config.token)
        finally:
            # Cleanup context managers when bot exits
            for cm in context_managers:
                await cm.__aexit__(None, None, None)
            
    except Exception as e:
        print(f"[red]Error starting bot:[/red] {str(e)}")
        raise