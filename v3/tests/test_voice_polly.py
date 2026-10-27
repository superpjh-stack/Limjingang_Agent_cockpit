import asyncio
import io

from v3.voice.polly import PollyVoice


class FakePolly:
    kwargs = None
    def synthesize_speech(self, **kwargs):
        self.kwargs = kwargs
        return {"AudioStream": io.BytesIO(b"abcdefgh")}


def test_polly_uses_korean_generative_pcm():
    async def collect():
        fake = FakePolly()
        voice = PollyVoice("ap-northeast-2", fake, chunk_bytes=3)
        chunks = [chunk async for chunk in voice.stream("출하 확인")]
        assert chunks == [b"abc", b"def", b"gh"]
        assert fake.kwargs["VoiceId"] == "Seoyeon"
        assert fake.kwargs["Engine"] == "generative"
        assert fake.kwargs["OutputFormat"] == "pcm"
        assert fake.kwargs["SampleRate"] == "16000"
    asyncio.run(collect())
