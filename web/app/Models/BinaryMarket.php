<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class BinaryMarket extends Model
{
    protected $fillable = [
        'symbol_id',
        'market_id',
        'question',
        'description',
        'category',
        'end_date',
        'status',
        'resolution',
    ];

    protected $casts = [
        'end_date' => 'datetime',
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
    ];

    /**
     * Get the symbol that owns this market.
     */
    public function symbol(): BelongsTo
    {
        return $this->belongsTo(Symbol::class);
    }

    /**
     * Get all positions for this market.
     */
    public function positions(): HasMany
    {
        return $this->hasMany(BinaryPosition::class, 'market_id', 'market_id');
    }

    /**
     * Get latest price data for this market.
     */
    public function latestPrice()
    {
        return $this->hasOne(BinaryPrice::class, 'symbol_id', 'symbol_id')
            ->orderBy('timestamp', 'desc');
    }

    /**
     * Scope to get active markets only.
     */
    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }

    /**
     * Scope to get markets by category.
     */
    public function scopeCategory($query, string $category)
    {
        return $query->where('category', $category);
    }

    /**
     * Scope to get markets ending soon.
     */
    public function scopeEndingSoon($query, int $days = 7)
    {
        return $query->where('end_date', '<=', now()->addDays($days))
            ->where('end_date', '>', now());
    }

    /**
     * Check if market is still active.
     */
    public function isActive(): bool
    {
        return $this->status === 'active' && $this->end_date > now();
    }

    /**
     * Get days until resolution.
     */
    public function daysUntilResolution(): int
    {
        return max(0, now()->diffInDays($this->end_date, false));
    }
}
