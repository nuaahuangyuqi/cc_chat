from ccask import Ask

with Ask(project="论文助手", memory=True, session_id="实验设计") as bot:
    print(bot.ask("我的研究方向是多模态检索").text)
    print(bot.ask("建议三个实验方向").text)
    bot.stop_memory()
    print(bot.ask("用一句话解释 Python 上下文管理器").text)
    bot.start_memory()
