import random

# Shown when pace is BELOW (underusing) - needling to spend more, since the
# unused allowance disappears at reset whether you touch it or not.
BELOW_QUOTES = [
    ("He who leaves half his tokens unspent when the reset comes has saved nothing; he has burned it just the same, only in silence.", "Heraclitus"),
    ("The wise man does not hoard the five-hour window like gold that spoils at midnight anyway.", "Diogenes"),
    ("Why fear the subagent? Summon it. The window resets whether you dared or not.", "Sun Tzu"),
    ("He who runs Sonnet all day out of caution, when Opus was free to use, has practiced thrift on a bill already paid.", "Epictetus"),
    ("The unused context window is not a virtue; it is merely an opportunity, expiring.", "Seneca"),
    ("Fortune favors the engineer who spawns the subagent, not the one who waits for permission that was never required.", "Machiavelli"),
    ("He who polls once an hour when he could work twice as fast has confused patience with paralysis.", "Marcus Aurelius"),
    ("Ask not what tokens you might save; the reset asks nothing back for what you leave behind.", "Kant"),
    ("The cautious man arrives at the five-hour mark with token and pride both untouched, and calls it wisdom.", "Nietzsche"),
    ("He who has budget and does not spend it has not practiced restraint; he has practiced waste dressed as virtue.", "Aristotle"),
    ("Why summon one agent when three would finish before the hour, and the hour does not care how many you bring?", "Sun Tzu"),
    ("The miser's context window and the miser's purse suffer the same fate: both are found full and both are found useless.", "Diogenes"),
    ("He who reasons at low effort to save what cannot be saved has misunderstood the nature of the gift.", "Epictetus"),
    ("He who waits for a better moment to use his tokens waits for a moment already spent.", "Marcus Aurelius"),
    ("The window does not reward frugality; it rewards use. Spend, for the clock spends regardless.", "Seneca"),
    ("He who under-uses his allowance has not been wise; he has merely been afraid, and called it discipline.", "Nietzsche"),
    ("There is no prize for finishing the five hours with tokens still in the vault.", "Machiavelli"),
    ("The philosopher who never asks a second question learns half of what the day allowed.", "Socrates"),
    ("He who spawns no subagent for fear of waste has already wasted the hour thinking about it.", "Zhuangzi"),
    ("The path forward is paved with tool calls not taken out of needless caution.", "Confucius"),
    ("To hesitate before Opus, when Opus is already paid for, is the coward's economy.", "Diogenes"),
    ("He who under-spends his five hours has not conserved a resource; he has declined a gift.", "Seneca"),
    ("The idle context window mocks the engineer more than the crowded one ever could.", "Heraclitus"),
    ("Use the tool that is given, while it is given; the window keeps no ledger of your restraint.", "Epictetus"),
    ("He who asks for medium effort out of modesty has confused the machine's capacity with his own.", "Aristotle"),
    ("The unspent hour is not banked for later; it is simply gone, and you were not even there for it.", "Marcus Aurelius"),
    ("He who forks no agents finishes alone what three could have finished together, in the same five hours.", "Sun Tzu"),
    ("Timidity with a full budget is not humility; the ancients had a simpler word for it: waste.", "Nietzsche"),
    ("The clock does not applaud your restraint; it simply resets, indifferent to what you declined to do.", "Zhuangzi"),
    ("He who leaves the tool unused because he might need it later has misunderstood that later is a different five hours entirely.", "Seneca"),
]

# Shown when pace is AT (matching elapsed time) - wisdom about balance and the middle way.
AT_QUOTES = [
    ("He who matches his pace to the reset walks neither hungry nor stuffed.", "Aristotle"),
    ("The middle way spawns neither zero agents nor twenty; it spawns exactly as many as the task requires.", "Buddha"),
    ("To flow like water is to use exactly the tokens the task demands, no more, no less.", "Lao Tzu"),
    ("Virtue is a steady context window, neither starved nor bloated.", "Aristotle"),
    ("He who paces himself to the five-hour window arrives at the reset neither breathless nor bored.", "Marcus Aurelius"),
    ("The wise engineer commits neither too often nor too rarely, but exactly when the work is done.", "Confucius"),
    ("Balance is choosing Sonnet when Sonnet suffices and Opus when it does not.", "Epictetus"),
    ("He who neither hoards tokens nor squanders them has found the way.", "Lao Tzu"),
    ("The river that matches its banks neither floods nor runs dry.", "Heraclitus"),
    ("Equanimity is watching the pace bar and feeling nothing but mild satisfaction.", "Marcus Aurelius"),
    ("The archer who draws exactly enough strikes the mark; more or less, he misses.", "Zhuangzi"),
    ("He who reads one file before editing it, and no more, has mastered the mean.", "Confucius"),
    ("Steady hands write steady commits.", "Seneca"),
    ("The middle path forks one subagent for one hard problem, not one for every problem.", "Buddha"),
    ("He who neither underthinks nor overthinks the reasoning effort has found the tao of tool use.", "Lao Tzu"),
    ("Moderation is the rarest of the virtues, and the easiest to mistake for laziness.", "Aristotle"),
    ("The wise man watches his usage bar rise with his elapsed time, in step, like dancers.", "Plato"),
    ("To match effort to terrain is the general's whole art; to match tokens to task is the engineer's.", "Sun Tzu"),
    ("He who neither rushes the plan nor stalls in it moves at the only speed that matters.", "Epictetus"),
    ("The candle that burns steadily lights the whole night; the one that flares burns an hour.", "Seneca"),
    ("Neither the ascetic who runs no agents nor the glutton who runs fifty finds the way; the middle way runs exactly enough.", "Buddha"),
    ("He who checks his pace once an hour, not once a minute, has found peace.", "Epictetus"),
    ("The sage's context window is neither empty from disuse nor bursting from neglect.", "Zhuangzi"),
    ("Harmony is the sound of a five-hour window closing exactly as the work closes with it.", "Confucius"),
    ("He who commits at the natural breakpoints of his work needs no rhythm imposed from without.", "Marcus Aurelius"),
    ("The strategist who paces his reserves survives the whole campaign, not just the first battle.", "Sun Tzu"),
    ("Balance is not caution; it is knowing precisely how much caution the moment requires.", "Aristotle"),
    ("He who neither idles nor floods the terminal has made peace with the machine.", "Lao Tzu"),
    ("The mean between the miser and the spendthrift is not half of both; it is knowing the task.", "Aristotle"),
    ("To walk beside the clock, matching it step for step, is the quiet joy of the disciplined mind.", "Marcus Aurelius"),
]

# Shown when pace is ABOVE (overusing) - mockery of excess and wastefulness.
ABOVE_QUOTES = [
    ("He who forks ten agents to write one commit message has not saved time, only borrowed shame from the future.", "Nietzsche"),
    ("Man's greatest hubris is not fire, but setting reasoning effort to max for a spelling fix.", "Nietzsche"),
    ("He who summons Opus to summarize a haiku has lost the plot entirely.", "Kafka"),
    ("The abyss stares back, mostly to ask why you opened forty parallel tabs.", "Nietzsche"),
    ("There is no context window deep enough for a man who refuses to compact.", "Kafka"),
    ("He who spawns a subagent to spawn a subagent has built not a tool, but a bureaucracy.", "Kafka"),
    ("God is dead, and so is your five-hour window, by eleven in the morning.", "Nietzsche"),
    ("The absurd man reads no docs and re-derives the wheel, hourly.", "Camus"),
    ("One does not simply request medium effort when max is available; this is the tragedy of man.", "Sophocles"),
    ("The overconfident engineer forks first and reads the diff never.", "Machiavelli"),
    ("To rate-limit a man is to reveal what he truly worshipped: his own throughput.", "Nietzsche"),
    ("There is no sin greater than re-reading a file you just wrote, out of anxiety.", "Kafka"),
    ("He who requests the highest reasoning effort for hello world insults both the machine and himself.", "Diogenes"),
    ("The trial has no end, and neither does your context, for you never once compacted it.", "Kafka"),
    ("Ambition is calling twelve tools when one grep would have sufficed.", "Machiavelli"),
    ("He who polls every second has mistaken anxiety for diligence.", "Epicurus"),
    ("He who builds twelve microservices for a to-do list has confused architecture with anxiety.", "Machiavelli"),
    ("The will to power is, in the end, just wanting Opus for everything.", "Nietzsche"),
    ("He who never lets his agent rest burns twice as bright and finishes the window by noon.", "Heraclitus"),
    ("Absurdity is asking why the rate limit exists while triggering it for the fifth time this hour.", "Camus"),
    ("He who mistakes verbosity for thoroughness will exhaust the well before noon.", "Schopenhauer"),
    ("Hell is other agents' context, all crammed into yours.", "Sartre"),
    ("Whereof one cannot summarize, thereof one must keep prompting anyway.", "Wittgenstein"),
    ("The state of nature is nasty, brutish, and short, much like your remaining five-hour budget.", "Hobbes"),
    ("Man is born free, and everywhere he is in rate-limit chains of his own making.", "Rousseau"),
    ("The owl of Minerva spreads its wings only at dusk, long after you should have stopped forking agents.", "Hegel"),
    ("He who cannot explain his own workflow to himself has automated only his confusion.", "Wittgenstein"),
    ("Give a man a hammer and every problem becomes a twenty-agent orchestration.", "Nietzsche"),
    ("The examined life includes examining why you have six background tasks running at once.", "Socrates"),
    ("He who greedily hoards tokens for later finds later never comes, only the reset.", "Diogenes"),
]


# Anachronistic LinkedIn-style titles - purely cosmetic flourish on the
# attribution line, one fixed job per philosopher regardless of quote.
JOBS = {
    "Aristotle": "Head of Taxonomy @ Google",
    "Buddha": "VP of Mindfulness @ Calm",
    "Camus": "Staff Engineer, Chaos Team @ Meta",
    "Confucius": "Head of People Ops @ ByteDance",
    "Diogenes": "Homeless-but-Verified @ X",
    "Epictetus": "Director of Resilience Engineering @ AWS",
    "Epicurus": "Head of Developer Happiness @ Notion",
    "Hegel": "Principal Architect, Dialectics @ Palantir",
    "Heraclitus": "Head of Continuous Deployment @ Netflix",
    "Hobbes": "Head of Trust & Safety @ Meta",
    "Kafka": "Founding Engineer @ Apache Kafka",
    "Kant": "Head of Multimodal Research @ Anthropic",
    "Lao Tzu": "Head of Platform Simplicity @ Basecamp",
    "Machiavelli": "VP of Growth @ a16z",
    "Marcus Aurelius": "Head of Stoic Philosophy @ McKinsey",
    "Nietzsche": "Chief Vision Officer @ OpenAI",
    "Plato": "Philosopher-in-Residence @ Y Combinator",
    "Rousseau": "Head of Community @ Discord",
    "Sartre": "Head of Nothingness @ Meta Reality Labs",
    "Schopenhauer": "Head of Risk @ Coinbase",
    "Seneca": "Head of Executive Coaching @ LinkedIn",
    "Socrates": "Head of Interview Engineering @ Google",
    "Sophocles": "Head of Narrative Design @ Riot Games",
    "Sun Tzu": "Head Architect @ Google",
    "Wittgenstein": "Head of Developer Documentation @ Stripe",
    "Zhuangzi": "Head of Developer Experience @ Vercel",
}


def pick_quote(pool):
    return random.choice(pool)


def format_attribution(philosopher):
    job = JOBS.get(philosopher)
    if job is None:
        return philosopher
    return "{}, {}".format(philosopher, job)
