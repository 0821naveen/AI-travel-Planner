import React from 'react';
import styles from './Chat.module.css';

interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
}

interface ChatProps {
  messages: Message[];
}

const Chat: React.FC<ChatProps> = ({ messages }) => (
  <div className={styles.chat}>
    {messages.map(msg => (
      <div key={msg.id} className={`${styles.message} ${styles[msg.sender]}`}>{msg.text}</div>
    ))}
  </div>
);

export default Chat;
