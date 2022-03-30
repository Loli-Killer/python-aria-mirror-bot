class _BotCommands:
    def __init__(self):
        self.StartCommand = 'start'

        self.MirrorCommand = 'mirror'
        self.MirrorManyCommand = 'mirrormany'
        self.UnzipMirrorCommand = 'unzipmirror'
        self.TarMirrorCommand = 'tarmirror'
        
        self.CloneCommand = "clone"
        self.WatchCommand = 'watch'
        self.TarWatchCommand = 'tarwatch'

        self.CancelMirror = 'cancel'
        self.CancelAllCommand = 'cancelall'

        self.ListCommand = 'list'
        self.StatusCommand = 'status'

        self.AuthorizeCommand = 'authorize'
        self.UnAuthorizeCommand = 'unauthorize'

        self.ChangeRootCommand = 'changeroot'
        self.PingCommand = 'ping'
        self.RestartCommand = 'restart'
        self.StatsCommand = 'stats'
        self.HelpCommand = 'help'
        self.LogCommand = 'log'

BotCommands = _BotCommands()
