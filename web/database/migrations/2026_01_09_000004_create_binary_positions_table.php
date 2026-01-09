<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Create binary_positions table for tracking arbitrage positions.
     *
     * Each position represents a paired YES+NO purchase:
     * - Buy YES at yes_entry_price
     * - Buy NO at no_entry_price
     * - Wait for market resolution
     * - Profit = $1.00 - (yes_entry_price + no_entry_price) - fees
     *
     * Position lifecycle:
     * 1. status='open' → Active position waiting for resolution
     * 2. status='resolved' → Market resolved, calculating P&L
     * 3. status='closed' → P&L settled, position archived
     */
    public function up(): void
    {
        Schema::create('binary_positions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('symbol_id')->constrained('symbols');
            $table->string('market_id', 100)->comment('Polymarket market ID');

            // Position details
            $table->decimal('yes_qty', 10, 4)->comment('Quantity of YES shares');
            $table->decimal('no_qty', 10, 4)->comment('Quantity of NO shares');
            $table->decimal('yes_entry_price', 10, 6)->comment('Entry price for YES');
            $table->decimal('no_entry_price', 10, 6)->comment('Entry price for NO');
            $table->decimal('entry_spread', 10, 6)->comment('yes_price + no_price at entry');

            // Order tracking
            $table->string('yes_order_id', 100)->nullable()->comment('Polymarket order ID for YES');
            $table->string('no_order_id', 100)->nullable()->comment('Polymarket order ID for NO');

            // Position status
            $table->string('status', 20)->default('open')->comment('open, resolved, closed, partial');
            $table->string('resolution', 10)->nullable()->comment('yes, no (after market resolves)');

            // P&L tracking
            $table->decimal('profit_loss', 10, 2)->nullable()->comment('Realized profit/loss');
            $table->decimal('profit_loss_pct', 6, 4)->nullable()->comment('P&L as % of cost');
            $table->decimal('fees_paid', 10, 2)->nullable()->comment('Total fees paid');

            // Timestamps
            $table->timestampTz('opened_at')->useCurrent()->comment('When position was opened');
            $table->timestampTz('closed_at')->nullable()->comment('When position was closed');
            $table->timestampTz('resolved_at')->nullable()->comment('When market was resolved');

            // Metadata
            $table->text('notes')->nullable()->comment('Any special notes or alerts');

            // Indexes for performance
            $table->index('symbol_id');
            $table->index('market_id');
            $table->index('status');
            $table->index('opened_at');
            $table->index(['status', 'opened_at'], 'idx_binary_positions_active');
        });
    }

    /**
     * Reverse the migration.
     */
    public function down(): void
    {
        Schema::dropIfExists('binary_positions');
    }
};
