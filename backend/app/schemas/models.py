from pydantic import BaseModel, Field
from typing import Optional


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    avatar_emoji: str = Field(default="👤", min_length=1, max_length=2)
    pin: str = Field(..., min_length=4, max_length=6, pattern=r"^\d+$")
    role: str = Field(default="member", pattern=r"^(admin|member)$")


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    avatar_emoji: Optional[str] = Field(None, min_length=1, max_length=2)
    pin: Optional[str] = Field(None, min_length=4, max_length=6, pattern=r"^\d+$")
    role: Optional[str] = Field(None, pattern=r"^(admin|member)$")
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    name: str
    avatar_emoji: str
    role: str
    is_active: bool
    last_login_at: Optional[str] = None
    created_at: str
    updated_at: str


class ProfileResponse(BaseModel):
    id: str
    name: str
    avatar_emoji: str
    is_active: bool


class LoginRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=6, pattern=r"^\d+$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: str
    end_time: str
    is_all_day: bool = False
    assigned_to_id: Optional[str] = None
    color_hex: Optional[str] = None


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_all_day: Optional[bool] = None
    assigned_to_id: Optional[str] = None
    color_hex: Optional[str] = None


class EventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: str
    end_time: str
    is_all_day: bool
    created_by_id: str
    assigned_to_id: Optional[str] = None
    color_hex: Optional[str] = None
    created_at: str
    updated_at: str


class CalendarSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1)
    color_hex: str = Field(default="#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")
    sync_interval_hours: int = Field(default=4, ge=1, le=168)


class CalendarSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    color_hex: Optional[str] = None
    sync_interval_hours: Optional[int] = None
    is_active: Optional[bool] = None


class CalendarSourceResponse(BaseModel):
    id: str
    name: str
    url: str
    color_hex: str
    sync_interval_hours: int
    last_synced_at: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str


class CalendarEventResponse(BaseModel):
    id: str
    source_id: str
    external_uid: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: str
    end_time: str
    all_day: bool
    color_hex: str
    synced_at: Optional[str] = None


class SyncLogResponse(BaseModel):
    id: str
    source_id: str
    events_imported: int
    events_deleted: int
    errors: list[str]
    started_at: str
    completed_at: Optional[str] = None
    status: str


class AnnouncementCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class AnnouncementResponse(BaseModel):
    id: str
    author_id: str
    content: str
    is_pinned: bool
    created_at: str
    updated_at: str


# Chore schemas
class ChoreCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    assignment_mode: str = Field(default="assigned", pattern=r"^(assigned|claimable)$")
    recurrence_rule: str = Field(..., min_length=1, max_length=500)
    default_assigned_to_id: Optional[str] = None
    point_value: int = Field(default=10, ge=1, le=1000)


class ChoreUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    assignment_mode: Optional[str] = Field(None, pattern=r"^(assigned|claimable)$")
    recurrence_rule: Optional[str] = None
    default_assigned_to_id: Optional[str] = None
    point_value: Optional[int] = Field(None, ge=1, le=1000)
    is_active: Optional[bool] = None


class ChoreResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    assignment_mode: str
    recurrence_rule: str
    default_assigned_to_id: Optional[str] = None
    point_value: int
    is_active: bool
    created_by_id: str
    created_at: str
    updated_at: str


class ChoreInstanceResponse(BaseModel):
    id: str
    chore_template_id: str
    assigned_to_id: Optional[str] = None
    due_date: str
    status: str
    claimed_by_id: Optional[str] = None
    claimed_at: Optional[str] = None
    completed_by_id: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str


class ChoreCompletionLogResponse(BaseModel):
    id: str
    instance_id: str
    completed_by_id: str
    completed_at: str
    points_earned: int


class ChoreStatsResponse(BaseModel):
    total_completed: int
    current_streak: int
    longest_streak: int
    points_earned: int


# Reward schemas
class RewardPointsLedgerEntry(BaseModel):
    id: str
    user_id: str
    points: int
    type: str
    reference_id: Optional[str] = None
    description: Optional[str] = None
    created_at: str


class AllowanceLedgerEntry(BaseModel):
    id: str
    user_id: str
    amount: str
    type: str
    reference_id: Optional[str] = None
    description: Optional[str] = None
    created_at: str


class RewardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    point_cost: int = Field(..., ge=1, le=100000)
    is_auto_fulfill: bool = False


class RewardUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    point_cost: Optional[int] = Field(None, ge=1, le=100000)
    is_auto_fulfill: Optional[bool] = None
    is_active: Optional[bool] = None


class RewardResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    point_cost: int
    is_auto_fulfill: bool
    is_active: bool
    created_by_id: str
    created_at: str
    updated_at: str


class RewardRequestCreate(BaseModel):
    pass


class RewardRequestResponse(BaseModel):
    id: str
    user_id: str
    reward_id: str
    status: str
    requested_at: str
    approved_at: Optional[str] = None
    approved_by_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class RewardResponseDetail(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    point_cost: int
    is_auto_fulfill: bool
    is_active: bool
    created_by_id: str
    created_at: str
    updated_at: str
    user_points_balance: int
    can_purchase: bool


class StreakResponse(BaseModel):
    user_id: str
    current_streak: int
    longest_streak: int
    last_completion_date: Optional[str] = None
    grace_days: int


class BadgeDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    icon: Optional[str] = None
    trigger_type: str = Field(..., pattern=r"^(streak|milestone)$")
    trigger_value: int = Field(..., ge=1, le=10000)
    points_reward: int = Field(default=0, ge=0, le=100000)


class BadgeDefinitionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    icon: Optional[str] = None
    trigger_type: Optional[str] = Field(None, pattern=r"^(streak|milestone)$")
    trigger_value: Optional[int] = Field(None, ge=1, le=10000)
    points_reward: Optional[int] = Field(None, ge=0, le=100000)


class BadgeDefinitionResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    trigger_type: str
    trigger_value: int
    points_reward: int
    created_at: str
    updated_at: str


class UserBadgeResponse(BaseModel):
    id: str
    user_id: str
    badge_definition_id: str
    earned_at: str


class AllowanceConfigUpdate(BaseModel):
    weekly_amount: str = Field(..., pattern=r"^\d+(\.\d{1,2})?$")


# DietaryTag schemas
class DietaryTagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color_hex: str = Field(default="#94a3b8", pattern=r"^#[0-9a-fA-F]{6}$")


class DietaryTagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color_hex: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    is_active: Optional[bool] = None


class DietaryTagResponse(BaseModel):
    id: str
    name: str
    color_hex: str
    is_active: bool = True
    created_at: str


# Recipe schemas
class RecipeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content_text: str = Field(..., min_length=1)
    ingredients_raw: Optional[str] = None
    steps_raw: Optional[str] = None
    dietary_tag_ids: list[str] = Field(default_factory=list)
    prep_time_min: Optional[int] = Field(None, ge=0)
    cook_time_min: Optional[int] = Field(None, ge=0)
    servings: Optional[int] = Field(None, ge=1)
    imported_from: Optional[str] = None


class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content_text: Optional[str] = None
    ingredients_raw: Optional[str] = None
    steps_raw: Optional[str] = None
    dietary_tag_ids: Optional[list[str]] = None
    prep_time_min: Optional[int] = None
    cook_time_min: Optional[int] = None
    servings: Optional[int] = None


class RecipeResponse(BaseModel):
    id: str
    title: str
    content_text: str
    ingredients_raw: Optional[str] = None
    steps_raw: Optional[str] = None
    dietary_tag_ids: list[str]
    dietary_tags: list[dict]
    prep_time_min: Optional[int] = None
    cook_time_min: Optional[int] = None
    servings: Optional[int] = None
    imported_from: Optional[str] = None
    created_by_id: str
    created_at: str
    updated_at: str


class RecipeImportRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None


# MealPlan schemas
class MealPlanCreate(BaseModel):
    meal_type: str = Field(..., pattern=r"^(breakfast|lunch|dinner|snack)$")
    date: str
    recipe_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = None


class MealPlanUpdate(BaseModel):
    meal_type: Optional[str] = None
    date: Optional[str] = None
    recipe_id: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None


class MealPlanResponse(BaseModel):
    id: str
    meal_type: str
    date: str
    recipe_id: Optional[str] = None
    title: str
    notes: Optional[str] = None
    recipe: Optional[dict] = None
    created_at: str
    updated_at: str


class MealPlanWeekResponse(BaseModel):
    week_start: str
    week_end: str
    meals: list[MealPlanResponse]


# ShoppingList schemas
class ShoppingListItemCreate(BaseModel):
    item: str = Field(..., min_length=1, max_length=200)
    quantity: Optional[str] = None
    is_persistent: bool = False
    meal_plan_id: Optional[str] = None


class ShoppingListItemUpdate(BaseModel):
    item: Optional[str] = None
    quantity: Optional[str] = None
    is_checked: Optional[bool] = None
    is_persistent: Optional[bool] = None


class ShoppingListItemResponse(BaseModel):
    id: str
    item: str
    quantity: Optional[str] = None
    is_checked: bool
    is_persistent: bool
    source: str
    meal_plan_id: Optional[str] = None
    created_by_id: str
    week_start_date: str
    checked_at: Optional[str] = None
    created_at: str
