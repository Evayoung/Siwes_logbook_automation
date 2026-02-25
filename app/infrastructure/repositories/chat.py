"""Chat repository for chat message operations.

This module provides repository methods for ChatMessage model with support
for conversation threads and unread message tracking.

Example:
    >>> from app.infrastructure.repositories.chat import ChatRepository
    >>> 
    >>> repo = ChatRepository(db)
    >>> messages = repo.get_conversation(user1_id, user2_id)
    >>> unread_count = repo.count_unread_messages(user_id)
"""

from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.infrastructure.repositories.base import BaseRepository
from app.domain.models.chat import ChatMessage


class ChatRepository(BaseRepository[ChatMessage]):
    """Repository for ChatMessage model operations.
    
    Extends BaseRepository with chat-specific queries including conversation
    threads, unread message tracking, and message marking.
    
    Example:
        >>> repo = ChatRepository(db)
        >>> messages = repo.get_conversation(student_id, supervisor_id)
    """
    
    def __init__(self, db: Session):
        """Initialize the chat repository.
        
        Args:
            db: The database session for queries
        """
        super().__init__(ChatMessage, db)
    
    def get_conversation(
        self,
        user1_id: str,
        user2_id: str,
        limit: int = 50
    ) -> List[ChatMessage]:
        """Get all messages in a conversation between two users.
        
        Args:
            user1_id: First user's ID
            user2_id: Second user's ID
            limit: Maximum number of messages to return (default: 50)
        
        Returns:
            List of ChatMessage instances ordered by creation time
        
        Example:
            >>> messages = repo.get_conversation(student_id, supervisor_id)
            >>> for msg in messages:
            ...     print(f"{msg.sender_id}: {msg.message_body}")
        """
        return self.db.query(ChatMessage).filter(
            or_(
                and_(
                    ChatMessage.sender_id == user1_id,
                    ChatMessage.receiver_id == user2_id
                ),
                and_(
                    ChatMessage.sender_id == user2_id,
                    ChatMessage.receiver_id == user1_id
                )
            )
        ).order_by(ChatMessage.created_at).limit(limit).all()
    
    def get_user_messages(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[ChatMessage]:
        """Get all messages sent to or from a user.
        
        Args:
            user_id: The user's ID
            limit: Maximum number of messages to return
        
        Returns:
            List of ChatMessage instances ordered by creation time descending
        
        Example:
            >>> messages = repo.get_user_messages(user_id, limit=20)
        """
        return self.db.query(ChatMessage).filter(
            or_(
                ChatMessage.sender_id == user_id,
                ChatMessage.receiver_id == user_id
            )
        ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
    
    def get_unread_messages(self, user_id: str) -> List[ChatMessage]:
        """Get all unread messages for a user.
        
        Args:
            user_id: The user's ID
        
        Returns:
            List of unread ChatMessage instances
        
        Example:
            >>> unread = repo.get_unread_messages(user_id)
            >>> print(f"You have {len(unread)} unread messages")
        """
        return self.db.query(ChatMessage).filter(
            ChatMessage.receiver_id == user_id,
            ChatMessage.is_read == False
        ).order_by(ChatMessage.created_at).all()
    
    def count_unread_messages(self, user_id: str) -> int:
        """Count unread messages for a user.
        
        Args:
            user_id: The user's ID
        
        Returns:
            Number of unread messages
        
        Example:
            >>> count = repo.count_unread_messages(user_id)
            >>> print(f"Unread: {count}")
        """
        return self.db.query(ChatMessage).filter(
            ChatMessage.receiver_id == user_id,
            ChatMessage.is_read == False
        ).count()
    
    def mark_as_read(self, message_ids: List[str]) -> int:
        """Mark messages as read.
        
        Args:
            message_ids: List of message IDs to mark as read
        
        Returns:
            Number of messages updated
        
        Example:
            >>> updated = repo.mark_as_read([msg1.id, msg2.id])
            >>> print(f"Marked {updated} messages as read")
        """
        result = self.db.query(ChatMessage).filter(
            ChatMessage.id.in_(message_ids)
        ).update(
            {"is_read": True},
            synchronize_session=False
        )
        self.db.flush()
        return result
    
    def mark_conversation_as_read(
        self,
        receiver_id: str,
        sender_id: str
    ) -> int:
        """Mark all messages in a conversation as read.
        
        Args:
            receiver_id: The receiver's user ID
            sender_id: The sender's user ID
        
        Returns:
            Number of messages updated
        
        Example:
            >>> updated = repo.mark_conversation_as_read(
            ...     receiver_id=student_id,
            ...     sender_id=supervisor_id
            ... )
        """
        result = self.db.query(ChatMessage).filter(
            ChatMessage.receiver_id == receiver_id,
            ChatMessage.sender_id == sender_id,
            ChatMessage.is_read == False
        ).update(
            {"is_read": True},
            synchronize_session=False
        )
        self.db.flush()
        return result
