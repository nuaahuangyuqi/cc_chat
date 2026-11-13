from ccask import Ask

# 默认 memory=0；这里带入最近 10 轮完整问答。
with Ask(project="论文助手", memory=10, session_id="实验设计") as bot:
    print(bot.ask("我的研究方向是多模态检索").text)
    print(bot.ask("建议三个实验方向").text)
    bot.set_memory(3)  # 后续最多带入最近 3 轮
    bot.stop_memory()  # 当前问题独立回答，成功问答仍保存
    print(bot.ask("用一句话解释 Python 上下文管理器").text)
    bot.start_memory()  # 恢复最近 3 轮
    print(bot.ask("继续讨论研究方向").text)
