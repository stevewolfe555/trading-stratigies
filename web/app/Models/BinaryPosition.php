<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class BinaryPosition extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'symbol_id',
        'market_id',
        'yes_qty',
        'no_qty',
        'yes_entry_price',
        'no_entry_price',
        'entry_spread',
        'yes_order_id',
        'no_order_id',
        'status',
        'resolution',
        'profit_loss',
        'profit_loss_pct',
        'fees_paid',
        'opened_at',
        'closed_at',
        'resolved_at',
        'notes',
    ];

    protected $casts = [
        'yes_qty' => 'decimal:4',
        'no_qty' => 'decimal:4',
        'yes_entry_price' => 'decimal:6',
        'no_entry_price' => 'decimal:6',
        'entry_spread' => 'decimal:6',
        'profit_loss' => 'decimal:2',
        'profit_loss_pct' => 'decimal:4',
        'fees_paid' => 'decimal:2',
        'opened_at' => 'datetime',
        'closed_at' => 'datetime',
        'resolved_at' => 'datetime',
    ];

    /**
     * Get the symbol that owns this position.
     */
    public function symbol(): BelongsTo
    {
        return $this->belongsTo(Symbol::class);
    }

    /**
     * Get the market for this position.
     */
    public function market(): BelongsTo
    {
        return $this->belongsTo(BinaryMarket::class, 'market_id', 'market_id');
    }

    /**
     * Scope to get open positions only.
     */
    public function scopeOpen($query)
    {
        return $query->where('status', 'open');
    }

    /**
     * Scope to get closed positions only.
     */
    public function scopeClosed($query)
    {
        return $query->where('status', 'closed');
    }

    /**
     * Scope to get resolved positions only.
     */
    public function scopeResolved($query)
    {
        return $query->where('status', 'resolved');
    }

    /**
     * Check if position is still open.
     */
    public function isOpen(): bool
    {
        return $this->status === 'open';
    }

    /**
     * Calculate total cost of position.
     */
    public function getTotalCostAttribute(): float
    {
        return (float) $this->yes_qty * (float) $this->yes_entry_price
            + (float) $this->no_qty * (float) $this->no_entry_price;
    }

    /**
     * Calculate locked profit (guaranteed if market resolves).
     */
    public function getLockedProfitAttribute(): float
    {
        // At resolution, we get $1.00 * quantity back
        // We paid entry_spread * average_quantity
        $avgQty = ((float) $this->yes_qty + (float) $this->no_qty) / 2;
        $payout = $avgQty * 1.00;
        $cost = $this->total_cost;

        return $payout - $cost;
    }

    /**
     * Calculate locked profit percentage.
     */
    public function getLockedProfitPctAttribute(): float
    {
        if ($this->total_cost == 0) {
            return 0;
        }
        return ($this->locked_profit / $this->total_cost) * 100;
    }

    /**
     * Get days position has been held.
     */
    public function getDaysHeldAttribute(): int
    {
        $endDate = $this->closed_at ?? now();
        return $this->opened_at->diffInDays($endDate);
    }

    /**
     * Get actual profit (after resolution).
     */
    public function getActualProfitAttribute(): ?float
    {
        if (!$this->profit_loss) {
            return null;
        }
        return (float) $this->profit_loss;
    }

    /**
     * Mark position as resolved.
     */
    public function markResolved(string $resolution, float $profitLoss, float $fees): void
    {
        $this->update([
            'status' => 'resolved',
            'resolution' => $resolution,
            'profit_loss' => $profitLoss,
            'profit_loss_pct' => $this->total_cost > 0 ? ($profitLoss / $this->total_cost) * 100 : 0,
            'fees_paid' => $fees,
            'resolved_at' => now(),
        ]);
    }

    /**
     * Close position.
     */
    public function close(): void
    {
        $this->update([
            'status' => 'closed',
            'closed_at' => now(),
        ]);
    }
}
