from ccask import Ask

# 显式带入最近 10 轮；支持服务端续接的接口也可改用 default_memory=True, memory=0。
with Ask(project="论文助手", default_memory=False, memory=10, session_id="实验设计") as bot:
    print(bot.ask("我的研究方向是多模态检索").text)
    print(bot.ask("建议三个实验方向").text)
    bot.set_memory(3)
    bot.stop_memory()
    print(bot.ask("用一句话解释 Python 上下文管理器").text)
    bot.start_memory()
    print(bot.ask("继续讨论研究方向").text)
    bot.clear_memory()  # 删除会话和名称；下一次 ask 自动使用新的随机会话。
