import React, { useRef, useCallback, useState, useEffect } from 'react';
import { Tooltip } from 'react-tooltip';
import type { SoundEntry } from '../types/words';

interface PronunciationProps {
  sounds: SoundEntry[];
}

const TOOLTIP_ID = 'pronunciation-tooltip';

type PlayState = 'idle' | 'playing' | 'error';

const Pronunciation: React.FC<PronunciationProps> = ({ sounds }) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [state, setState] = useState<PlayState>('idle');

  const sources = sounds.flatMap((s) => {
    const result: Array<{ src: string; type: string }> = [];
    if (s.mp3_url) result.push({ src: s.mp3_url, type: 'audio/mpeg' });
    if (s.ogg_url) result.push({ src: s.ogg_url, type: 'audio/ogg' });
    return result;
  });

  const hasAudio = sources.length > 0;
  const ipa = sounds.find((s) => s.ipa)?.ipa;

  const play = useCallback(() => {
    if (!hasAudio || state === 'playing') return;
    setState('playing');
    audioRef.current?.play().catch(() => setState('error'));
  }, [hasAudio, state]);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    const onEnded = () => setState('idle');
    const onError = () => setState('idle');
    el.addEventListener('ended', onEnded);
    el.addEventListener('error', onError);
    return () => {
      el.removeEventListener('ended', onEnded);
      el.removeEventListener('error', onError);
    };
  }, []);

  const tooltip = hasAudio
    ? ipa
      ? `Play ${ipa}`
      : 'Play'
    : 'No audio available';

  return (
    <span className="pronunciation">
      {hasAudio && (
        <audio ref={audioRef} preload="none">
          {sources.map((s, i) => (
            <source key={i} src={s.src} type={s.type} />
          ))}
        </audio>
      )}
      <button
        className={`pronunciation-play${!hasAudio ? ' pronunciation-play--missing' : ''}${state === 'playing' ? ' pronunciation-play--active' : ''}`}
        onClick={play}
        disabled={!hasAudio || state === 'playing'}
        data-tooltip-id={TOOLTIP_ID}
        data-tooltip-content={tooltip}
        aria-label={tooltip}
      >
        {state === 'playing' ? '⋯' : '\u25B6'}
      </button>
      <Tooltip id={TOOLTIP_ID} place="top" className="tooltip" />
    </span>
  );
};

export default Pronunciation;
