import React, { useEffect, useRef } from 'react';

export default function StoryChat({ messages, busy }) {
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, busy]);
  return (
    <div className="story-scroll" role="log" aria-live="polite" aria-label="Story">
      <div className="story-feed">
        {messages.map((message, i) => (
          <div className={'story-message ' + (message.by === 'player' ? 'player-message' : 'narrator-message')} key={i}>
            
            {message.text.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
          </div>
        ))}
        {busy && <div className="typing-indicator" role="status">The story is unfolding <span className="typing-dots">···</span></div>}
        <div ref={endRef} />
      </div>
    </div>
  );
}
