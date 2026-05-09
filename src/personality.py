#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
personality.py — 人格分析模块
生成 Big Five 和 MBTI 分析结果，包含好友备注推荐标签
"""

import json
import re
from typing import Dict, List, Optional
from collections import Counter


def analyze_communication_style(messages: List[str], member_name: str) -> Dict:
    """
    分析沟通风格，生成人格分析结果

    Args:
        messages: 消息列表
        member_name: 成员名称

    Returns:
        包含 Big Five, MBTI, 风格标签的字典
    """
    if not messages:
        return {}

    # 基本统计
    total_msgs = len(messages)
    total_chars = sum(len(m) for m in messages)
    avg_length = total_chars / total_msgs if total_msgs > 0 else 0

    # 关键词统计
    all_text = ' '.join(messages)

    # 情感关键词
    positive_words = ['哈哈', '好的', '不错', '厉害', '棒', '赞', '好的', '谢谢', '感谢', '喜欢']
    negative_words = ['烦', '累', '讨厌', '无语', '唉', '哎', '郁闷', '焦虑']
    question_marks = all_text.count('?') + all_text.count('？')

    # 工作相关
    work_words = ['项目', '需求', '产品', '开发', '测试', '上线', 'bug', 'Bug', '会议', '报告', '方案']
    planning_words = ['明天', '下周', '计划', '安排', '时候', '到时候', '提前']

    # 人际互动
    mention_pattern = r'@[一-龥a-zA-Z0-9_]+'
    mentions = len(re.findall(mention_pattern, all_text))

    # 计算各项指标
    positive_count = sum(all_text.count(w) for w in positive_words)
    negative_count = sum(all_text.count(w) for w in negative_words)
    work_count = sum(all_text.count(w) for w in work_words)
    planning_count = sum(all_text.count(w) for w in planning_words)

    opinion_rate = sum(1 for m in messages if any(w in m for w in ['我觉得', '我认为', '应该', '建议'])) / total_msgs * 100
    question_rate = question_marks / total_msgs * 100 if total_msgs > 0 else 0

    # 计算 Big Five 分数
    big5 = _compute_big5(
        avg_length, opinion_rate, question_rate,
        positive_count, negative_count, work_count,
        planning_count, mentions, total_msgs
    )

    # 计算 MBTI
    mbti = _compute_mbti(big5, avg_length, work_count, planning_count, total_msgs)

    # 生成风格标签和备注推荐
    style = _generate_style(big5, mbti, member_name, messages, avg_length)

    return {
        'nickname': member_name,
        'big5': big5,
        'mbti': mbti,
        'style': style
    }


def _compute_big5(avg_length: float, opinion_rate: float, question_rate: float,
                  positive_count: int, negative_count: int, work_count: int,
                  planning_count: int, mentions: int, total_msgs: int) -> Dict:
    """计算 Big Five 人格维度"""

    # 开放性：基于话题广度和表达长度
    openness = min(100, max(0, 50 + int(avg_length * 0.5) + int(work_count * 0.5)))

    # 尽责性：基于计划性词汇和话题专注度
    conscientiousness = min(100, max(0, 50 + int(planning_count * 0.8) + int(work_count * 0.3)))

    # 外向性：基于互动频率和表达长度
    extraversion = min(100, max(0, 50 + int(mentions * 2) + int(avg_length * 0.3)))

    # 宜人性：基于正面/负面词汇比例
    if positive_count + negative_count > 0:
        agreeableness = min(100, max(0, 50 + int((positive_count - negative_count) * 2)))
    else:
        agreeableness = 55

    # 神经质：基于负面情绪和问题频率
    neuroticism = min(100, max(0, 50 + int(negative_count * 1.5) - int(positive_count * 0.5)))

    return {
        'openness': {
            'score': openness,
            'description': _get_openness_desc(openness)
        },
        'conscientiousness': {
            'score': conscientiousness,
            'description': _get_conscientiousness_desc(conscientiousness)
        },
        'extraversion': {
            'score': extraversion,
            'description': _get_extraversion_desc(extraversion)
        },
        'agreeableness': {
            'score': agreeableness,
            'description': _get_agreeableness_desc(agreeableness)
        },
        'neuroticism': {
            'score': neuroticism,
            'description': _get_neuroticism_desc(neuroticism)
        }
    }


def _get_openness_desc(score: int) -> str:
    if score >= 75:
        return "对新事物充满好奇，喜欢探索不同领域。思维开放，愿意接受新观点和方法。"
    elif score >= 60:
        return "保持适度的好奇心，愿意尝试新方法。对专业领域有持续关注和探索。"
    else:
        return "偏好稳定和熟悉的环境，对变化持谨慎态度。"


def _get_conscientiousness_desc(score: int) -> str:
    if score >= 75:
        return "做事认真负责，对任务有明确的规划和执行。注重细节和流程规范。"
    elif score >= 60:
        return "对工作有责任感，能够跟进问题。关注执行但也能灵活调整。"
    else:
        return "做事相对随性，对细节关注较少。"


def _get_extraversion_desc(score: int) -> str:
    if score >= 75:
        return "表达活跃，善于社交和互动。喜欢分享和交流，沟通积极主动。"
    elif score >= 60:
        return "表达适度，在合适的场合善于沟通。注重有意义的深度交流。"
    else:
        return "相对内敛，更倾向于倾听和观察。"


def _get_agreeableness_desc(score: int) -> str:
    if score >= 75:
        return "善于理解他人，注重维护关系和谐。在讨论中保持友善和包容。"
    elif score >= 60:
        return "能够配合团队，有自己的判断但表达方式温和。"
    else:
        return "更倾向于直接表达观点，在讨论中坚持自己的立场。"


def _get_neuroticism_desc(score: int) -> str:
    if score >= 70:
        return "情绪波动较大，容易感受到压力和焦虑。需要更多的情绪调节支持。"
    elif score >= 55:
        return "偶尔会有情绪波动，但整体能够自我调节。"
    else:
        return "情绪稳定，面对压力能够理性应对。心态平和。"


def _compute_mbti(big5: Dict, avg_length: float, work_count: int,
                  planning_count: int, total_msgs: int) -> Dict:
    """计算 MBTI 类型"""

    openness = big5['openness']['score']
    conscientiousness = big5['conscientiousness']['score']
    extraversion = big5['extraversion']['score']
    agreeableness = big5['agreeableness']['score']

    # E vs I
    ei_lean = 'E' if extraversion >= 55 else 'I'
    ei_strength = max(50, extraversion) if ei_lean == 'E' else max(50, 100 - extraversion)

    # S vs N
    sn_lean = 'N' if openness >= 60 else 'S'
    sn_strength = max(50, openness) if sn_lean == 'N' else max(50, 100 - openness)

    # T vs F
    tf_lean = 'F' if agreeableness >= 55 else 'T'
    tf_strength = max(50, agreeableness) if tf_lean == 'F' else max(50, 100 - agreeableness)

    # J vs P
    jp_lean = 'J' if conscientiousness >= 55 else 'P'
    jp_strength = max(50, conscientiousness) if jp_lean == 'J' else max(50, 100 - conscientiousness)

    mbti_type = ei_lean + sn_lean + tf_lean + jp_lean

    mbti_names = {
        'INTJ': '建筑师', 'INTP': '逻辑学家', 'ENTJ': '指挥官', 'ENTP': '辩论家',
        'INFJ': '提倡者', 'INFP': '调停者', 'ENFJ': '主人公', 'ENFP': '竞选者',
        'ISTJ': '物流师', 'ISFJ': '守护者', 'ESTJ': '总经理', 'ESTP': '企业家',
        'ISTP': '鉴赏家', 'ISFP': '探险家', 'ESFJ': '执政官', 'ESFP': '表演者'
    }

    return {
        'type': mbti_type,
        'name': mbti_names.get(mbti_type, ''),
        'confidence': '较高',
        'note': _get_mbti_note(mbti_type),
        'dims': {
            'EI': {'lean': f'{ei_lean} ({"外向" if ei_lean == "E" else "内向"})', 'strength': f'{ei_strength}%', 'reason': f'表达{"活跃" if ei_lean == "E" else "适中"}，{"善于互动" if ei_lean == "E" else "注重深度交流"}'},
            'SN': {'lean': f'{sn_lean} ({"直觉" if sn_lean == "N" else "感觉"})', 'strength': f'{sn_strength}%', 'reason': f'{"关注趋势和方向" if sn_lean == "N" else "关注具体和实际"}'},
            'TF': {'lean': f'{tf_lean} ({"思考" if tf_lean == "T" else "情感"})', 'strength': f'{tf_strength}%', 'reason': f'{"偏理性分析" if tf_lean == "T" else "考虑他人感受"}'},
            'JP': {'lean': f'{jp_lean} ({"判断" if jp_lean == "J" else "知觉"})', 'strength': f'{jp_strength}%', 'reason': f'{"做事有计划" if jp_lean == "J" else "保持灵活开放"}'}
        }
    }


def _get_mbti_note(mbti_type: str) -> str:
    notes = {
        'INTJ': '建筑师型人格：善于规划，追求效率和完美。具有战略思维，喜欢独立思考。',
        'INTP': '逻辑学家型人格：善于分析，对理论和概念有浓厚兴趣。追求逻辑一致性。',
        'ENTJ': '指挥官型人格：善于领导和组织，目标明确。喜欢推动事情向前发展。',
        'ENTP': '辩论家型人格：思维敏捷，善于发现问题。喜欢探索新思路和可能性。',
        'INFJ': '提倡者型人格：内省深思，善于洞察。关注长远价值和意义。',
        'INFP': '调停者型人格：理想主义，追求真实和美好。对人有深刻的理解。',
        'ENFJ': '主人公型人格：善于激励他人，关注团队发展。具有领导魅力。',
        'ENFP': '竞选者型人格：热情洋溢，善于发现可能性。喜欢与人交流想法。',
        'ISTJ': '物流师型人格：务实可靠，注重细节和规范。做事有始有终。',
        'ISFJ': '守护者型人格：温和体贴，善于照顾他人。注重传统和稳定。',
        'ESTJ': '总经理型人格：善于管理，注重效率和组织。喜欢明确的规则。',
        'ESTP': '企业家型人格：行动力强，善于把握机会。喜欢冒险和挑战。',
        'ISTP': '鉴赏家型人格：务实冷静，善于解决问题。喜欢动手实践。',
        'ISFP': '探险家型人格：温和敏感，追求美感和和谐。有艺术气质。',
        'ESFJ': '执政官型人格：善于协调，关注团队和谐。喜欢帮助他人。',
        'ESFP': '表演者型人格：热情活泼，善于活跃气氛。享受当下。'
    }
    return notes.get(mbti_type, '')


def _generate_style(big5: Dict, mbti: Dict, name: str, messages: List[str], avg_length: float) -> Dict:
    """生成沟通风格和好友备注推荐"""

    openness = big5['openness']['score']
    conscientiousness = big5['conscientiousness']['score']
    extraversion = big5['extraversion']['score']
    agreeableness = big5['agreeableness']['score']

    mbti_type = mbti['type']

    # 生成一句话风格标签（用于好友备注）
    remark_tag = _generate_remark_tag(mbti_type, big5)

    # 生成详细总结
    summary = _generate_summary(mbti_type, big5, name)

    # 生成优势列表
    strengths = _generate_strengths(mbti_type, big5)

    # 生成趣味事实
    fun_facts = _generate_fun_facts(messages, avg_length, name)

    return {
        'one_line': remark_tag,
        'remark_tag': remark_tag,  # 专门用于好友备注的标签
        'summary': summary,
        'strengths': strengths,
        'fun_facts': fun_facts
    }


def _generate_remark_tag(mbti_type: str, big5: Dict) -> str:
    """生成适合好友备注的一句话标签"""

    tags = {
        'INTJ': '冷静的战略规划者，用系统思维解决问题',
        'INTP': '深邃的逻辑分析师，用理性探索世界',
        'ENTJ': '果断的领导者，用目标驱动团队前进',
        'ENTP': '敏捷的辩论家，用创新推动讨论',
        'INFJ': '温和的洞察者，用深度理解人心',
        'INFP': '理想主义的调停者，用真诚触动他人',
        'ENFJ': '热情的激励者，用魅力凝聚团队',
        'ENFP': '活力的探索者，用热情感染周围',
        'ISTJ': '可靠的执行者，用细节保证质量',
        'ISFJ': '温柔的守护者，用关怀照顾他人',
        'ESTJ': '高效的管理者，用规则推动执行',
        'ESTP': '行动的企业家，用冒险把握机会',
        'ISTP': '务实的鉴赏家，用技能解决问题',
        'ISFP': '敏感的艺术家，用美感丰富生活',
        'ESFJ': '热情的协调者，用沟通推动协作',
        'ESFP': '活泼的表演者，用快乐感染他人'
    }

    base_tag = tags.get(mbti_type, '独特的个性，值得深入了解')

    # 根据具体分数微调
    if big5['openness']['score'] >= 75:
        base_tag = base_tag.replace('用', '善于探索，用')
    if big5['extraversion']['score'] <= 50:
        base_tag = base_tag.replace('热情的', '温和的').replace('活泼的', '安静的')

    return base_tag


def _generate_summary(mbti_type: str, big5: Dict, name: str) -> str:
    """生成详细风格总结"""
    openness_desc = "开放好奇" if big5['openness']['score'] >= 65 else "稳重务实"
    social_desc = "善于表达" if big5['extraversion']['score'] >= 60 else "内敛沉稳"
    work_desc = "注重规划" if big5['conscientiousness']['score'] >= 65 else "灵活应变"

    return f"{name}是一位{openness_desc}、{social_desc}的人。{work_desc}，在交流中展现出{mbti_type}类型的典型特征。"


def _generate_strengths(mbti_type: str, big5: Dict) -> List[str]:
    """生成优势列表"""

    base_strengths = {
        'INT': ['思维缜密，善于分析', '独立思考，追求完美', '具有战略眼光'],
        'ENT': ['领导力强，目标明确', '善于组织推动', '决策果断'],
        'INF': ['洞察力强，善解人意', '理想主义，追求意义', '温和而有原则'],
        'ENF': ['善于激励他人', '团队意识强', '表达有感染力'],
        'IST': ['踏实可靠，注重细节', '执行力强', '遵守规范'],
        'EST': ['管理能力强', '注重效率', '善于处理实际问题'],
        'ISF': ['善于照顾他人', '温和体贴', '注重传统和稳定'],
        'ESF': ['善于协调沟通', '热情友善', '关注团队和谐'],
        'IST': ['务实冷静', '善于解决问题', '灵活应变'],
        'ISF': ['温和敏感', '有艺术气质', '追求和谐'],
        'ESF': ['善于活跃气氛', '热情活泼', '善于社交'],
        'ESP': ['行动力强', '善于把握机会', '享受当下']
    }

    # 简化逻辑，根据 MBTI 首字母选择
    if mbti_type.startswith('I'):
        if mbti_type[1] == 'N':
            return ['善于深度思考', '有独特的见解', '追求内在价值']
        else:
            return ['务实可靠', '注重细节', '执行力强']
    else:
        if mbti_type[1] == 'N':
            return ['善于领导激励', '有远见卓识', '推动力强']
        else:
            return ['善于协调沟通', '行动力强', '注重实效']


def _generate_fun_facts(messages: List[str], avg_length: float, name: str) -> List[str]:
    """生成趣味事实"""

    facts = []

    if avg_length < 15:
        facts.append(f'平均消息长度{avg_length:.1f}字，表达简洁高效')
    elif avg_length > 25:
        facts.append(f'平均消息长度{avg_length:.1f}字，表达详尽细致')

    # 分析高频词
    words = []
    for m in messages:
        words.extend([w for w in m.split() if len(w) >= 2])
    word_freq = Counter(words)

    if word_freq:
        top_word = word_freq.most_common(1)[0][0]
        facts.append(f'高频词"{top_word}"，反映了个人关注点')

    return facts if facts else [f'{name}的聊天风格独特，值得深入了解']


def generate_remark_tags_batch(results: Dict[str, Dict]) -> Dict[str, str]:
    """
    批量生成好友备注标签

    Args:
        results: 成员名 -> 分析结果的映射

    Returns:
        成员名 -> 备注标签的映射
    """
    tags = {}
    for name, result in results.items():
        if result and 'style' in result:
            tags[name] = result['style'].get('remark_tag', result['style'].get('one_line', ''))
    return tags


if __name__ == '__main__':
    # 测试
    test_messages = [
        "我觉得这个方案可以",
        "明天我们讨论一下",
        "哈哈好的",
        "项目进度怎么样了",
        "需要我帮忙吗"
    ]
    result = analyze_communication_style(test_messages, "测试用户")
    print(json.dumps(result, ensure_ascii=False, indent=2))
