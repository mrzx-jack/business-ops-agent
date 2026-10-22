
from app.agents.llm import get_llm


def main():
    llm = get_llm()

    response = llm.invoke(
        "请用一句话介绍你自己，并说明你能否帮助查询企业客户信息。"
    )

    print("模型调用成功")
    print("模型回复：")
    print(response.content)


if __name__ == "__main__":
    main()
