# GunsmithBot

Python Discord bot to retrieve weapon rolls for Destiny 2.

This project is no longer being worked on due to development of discord.py having been discontinued.

## Requirements

- Python 3.8
- [discord.py](https://github.com/Rapptz/discord.py)
- [pydest](https://github.com/jgayfer/pydest)
  - Used to handle downloading and updating Bungie's manifest
- [aiosqlite](https://github.com/jreese/aiosqlite)
- [pytest](https://docs.pytest.org/en/latest/getting-started.html)

## Setup

Set your Discord API key to `DISCORD_KEY` as an environment variable

Set your Bungie API key to `BUNGIE_KEY` as an environment variable

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Resources/Attributions

[Destiny 2 API Info - vpzed](https://github.com/vpzed/Destiny2-API-Info/wiki/)
- An excellent guide to understanding Bungie's API and navigating the manifest SQLite database
  
[Bungie.net API Wiki](https://github.com/Bungie-net/api/wiki/)

## License

[MIT](./LICENSE)
